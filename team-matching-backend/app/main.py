import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.db import DB, engine, rows
from app.routers import projects, requests, skills, students, teams
from app.schemas import Dashboard, ErrorResponse, Health

settings = get_settings()
logger = logging.getLogger(__name__)
key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def check_api_key(key: str | None = Security(key_header)):
    if settings.api_key and (not key or not secrets.compare_digest(key, settings.api_key)):
        raise HTTPException(401, "Missing or invalid X-API-Key")


@asynccontextmanager
async def lifespan(app):
    yield
    engine.dispose()


app = FastAPI(
    title="Team Matching System API",
    version="1.0.0",
    lifespan=lifespan,
    responses={code: {"model": ErrorResponse} for code in (401, 404, 409, 422, 503)},
    description="Backend for the supplied DBMS schema. Local classroom demo: "
    "there are no student passwords or ownership roles in the source database. "
    "An optional shared X-API-Key protects API access, but does not identify individual students.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc):
    return JSONResponse(
        status_code=exc.status_code, content={"error": {"message": str(exc.detail)}}, headers=exc.headers
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc):
    issues = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"message": "Validation failed", "details": issues}})


@app.exception_handler(DBAPIError)
async def database_error(request: Request, exc):
    args = getattr(exc.orig, "args", ())
    code = args[0] if args else None
    messages = {
        1062: "A record with that unique value already exists",
        1451: "This record is still referenced by other records",
        1452: "A referenced record does not exist",
        3819: "A database validation rule was violated",
        1205: "Concurrent update conflict; retry the request",
        1213: "Concurrent update conflict; retry the request",
    }
    if code == 1644:
        message, status = str(args[1]), 409  # Messages emitted by supplied business-rule triggers.
    elif code in messages:
        message, status = messages[code], 409
    else:
        logger.error("Database operation failed (driver code %s)", code)
        message, status = "Database unavailable or not initialized", 503
    return JSONResponse(status_code=status, content={"error": {"message": message}})


@app.get("/", include_in_schema=False)
def root():
    return {"name": "Team Matching System API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["Health"], response_model=Health)
def health(db: DB):
    rows(db, "SELECT 1 FROM STUDENT LIMIT 1")
    return {"status": "ok", "database": "connected"}


api = APIRouter(prefix="/api", dependencies=[Depends(check_api_key)])
for router in (students.router, projects.router, teams.router, skills.router, requests.router):
    api.include_router(router)


@api.get("/dashboard", tags=["Dashboard"], response_model=Dashboard)
def dashboard(db: DB):
    return rows(
        db,
        "SELECT (SELECT COUNT(*) FROM STUDENT) AS students, "
        "(SELECT COUNT(*) FROM TEAM) AS teams, (SELECT COUNT(*) FROM PROJECT) AS projects, "
        "(SELECT COUNT(*) FROM STUDENT WHERE Availability_Status = 'Available' AND Team_id IS NULL) AS available_students, "
        "(SELECT COUNT(*) FROM REQUEST_TO_JOIN WHERE Request_status = 'Pending') AS pending_requests",
    )[0]


app.include_router(api)
