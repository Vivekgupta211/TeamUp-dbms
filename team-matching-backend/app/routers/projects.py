from fastapi import APIRouter, Query

from app.db import DB, conflict, insert, one, rows, run, update
from app.schemas import ID, Message, Project, ProjectCreate, ProjectPatch

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=list[Project])
def list_projects(
    db: DB,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, pattern="^(Open|In Progress|Closed)$"),
    category: str | None = Query(None, max_length=100),
):
    return rows(
        db,
        "SELECT * FROM PROJECT WHERE (:status IS NULL OR Status = :status) "
        "AND (:category IS NULL OR Category = :category) ORDER BY Project_id LIMIT :limit OFFSET :offset",
        status=status,
        category=category,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=Project, status_code=201)
def create_project(body: ProjectCreate, db: DB):
    if body.created_by_student_id is not None:
        one(db, "STUDENT", "Student_id", body.created_by_student_id)
    return one(db, "PROJECT", "Project_id", insert(db, "PROJECT", body.model_dump()))


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: ID, db: DB):
    return one(db, "PROJECT", "Project_id", project_id)


@router.patch("/{project_id}", response_model=Project)
def patch_project(project_id: ID, body: ProjectPatch, db: DB):
    existing = one(db, "PROJECT", "Project_id", project_id, lock=True)
    data = body.model_dump(exclude_unset=True)
    merged = existing | data
    if bool(merged["is_official"]) == (merged["created_by_student_id"] is not None):
        conflict("Official projects need a null creator; student projects need a creator ID")
    if merged["created_by_student_id"] is not None:
        one(db, "STUDENT", "Student_id", merged["created_by_student_id"])
    update(db, "PROJECT", "Project_id", project_id, data)
    return one(db, "PROJECT", "Project_id", project_id)


@router.delete("/{project_id}", response_model=Message)
def delete_project(project_id: ID, db: DB):
    one(db, "PROJECT", "Project_id", project_id, lock=True)
    if rows(db, "SELECT Team_id FROM TEAM WHERE Project_id = :id LIMIT 1", id=project_id):
        conflict("Delete the project's teams first")
    run(db, "DELETE FROM PROJECT WHERE Project_id = :id", id=project_id)
    return {"message": "Project deleted"}
