from fastapi import APIRouter, Query

from app.db import DB, conflict, insert, one, rows, run, update
from app.schemas import ID, JoinRequest, Message, RequestCreate, RequestDecision
from app.services import accepting_team

router = APIRouter(prefix="/requests", tags=["Join requests"])


@router.get("", response_model=list[JoinRequest])
def list_requests(
    db: DB,
    student_id: ID | None = None,
    team_id: ID | None = None,
    status: str | None = Query(None, pattern="^(Pending|Approved|Rejected)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return rows(
        db,
        "SELECT * FROM REQUEST_TO_JOIN WHERE (:student IS NULL OR Student_id = :student) "
        "AND (:team IS NULL OR Team_id = :team) AND (:status IS NULL OR Request_status = :status) "
        "ORDER BY Request_id DESC LIMIT :limit OFFSET :offset",
        student=student_id,
        team=team_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=JoinRequest, status_code=201)
def create_request(body: RequestCreate, db: DB):
    student = one(db, "STUDENT", "Student_id", body.student_id, lock=True)
    team = one(db, "TEAM", "Team_id", body.team_id, lock=True)
    if student["team_id"] is not None or student["availability_status"] != "Available":
        conflict("Only available students without a team may request to join")
    accepting_team(db, team)
    if rows(
        db,
        "SELECT Request_id FROM REQUEST_TO_JOIN WHERE Student_id = :student "
        "AND Team_id = :team AND Request_status = 'Pending'",
        student=body.student_id,
        team=body.team_id,
    ):
        conflict("A pending request already exists for this student and team")
    request_id = insert(db, "REQUEST_TO_JOIN", body.model_dump())
    return one(db, "REQUEST_TO_JOIN", "Request_id", request_id)


@router.get("/{request_id}", response_model=JoinRequest)
def get_request(request_id: ID, db: DB):
    return one(db, "REQUEST_TO_JOIN", "Request_id", request_id)


def lock_request(db, request_id):
    existing = one(db, "REQUEST_TO_JOIN", "Request_id", request_id)
    student = one(db, "STUDENT", "Student_id", existing["student_id"], lock=True)
    team = one(db, "TEAM", "Team_id", existing["team_id"], lock=True)
    request = one(db, "REQUEST_TO_JOIN", "Request_id", request_id, lock=True)
    if request["request_status"] != "Pending":
        conflict("Only pending requests can be decided or withdrawn")
    return student, team


@router.patch("/{request_id}", response_model=JoinRequest)
def decide_request(request_id: ID, body: RequestDecision, db: DB):
    student, team = lock_request(db, request_id)
    if body.request_status == "Approved":
        if student["team_id"] is not None or student["availability_status"] != "Available":
            conflict("Student is no longer available to join a team")
        accepting_team(db, team)
    # The original SQL trigger applies membership and marks full teams.
    update(db, "REQUEST_TO_JOIN", "Request_id", request_id, body.model_dump())
    if body.request_status == "Approved":
        # Other applications become invalid once this student joins a team.
        run(
            db,
            "UPDATE REQUEST_TO_JOIN SET Request_status = 'Rejected' WHERE Student_id = :student "
            "AND Request_id <> :request AND Request_status = 'Pending'",
            student=student["student_id"],
            request=request_id,
        )
    return one(db, "REQUEST_TO_JOIN", "Request_id", request_id)


@router.delete("/{request_id}", response_model=Message)
def withdraw_request(request_id: ID, db: DB):
    lock_request(db, request_id)
    run(db, "DELETE FROM REQUEST_TO_JOIN WHERE Request_id = :id", id=request_id)
    return {"message": "Pending request withdrawn"}
