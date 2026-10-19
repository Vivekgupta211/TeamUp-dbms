from fastapi import APIRouter, Query

from app.db import DB, conflict, insert, one, rows, run, update
from app.schemas import ID, Message, SkillIDs, Student, Team, TeamCreate, TeamDetail, TeamPatch
from app.services import member_count, remove_member, replace_skills, student_detail, team_detail

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=list[Team])
def list_teams(
    db: DB,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    project_id: ID | None = None,
    status: str | None = Query(None, pattern="^(Forming|Active|Full|Closed)$"),
):
    found = rows(
        db,
        "SELECT Team_id FROM TEAM WHERE (:project IS NULL OR Project_id = :project) "
        "AND (:status IS NULL OR team_status = :status) ORDER BY Team_id LIMIT :limit OFFSET :offset",
        project=project_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [team_detail(db, t["team_id"]) for t in found]


@router.post("", response_model=TeamDetail, status_code=201)
def create_team(body: TeamCreate, db: DB):
    project = one(db, "PROJECT", "Project_id", body.project_id, lock=True)
    if project["status"] == "Closed":
        conflict("Cannot create a team for a closed project")
    return team_detail(db, insert(db, "TEAM", body.model_dump()), members=True)


@router.get("/{team_id}", response_model=TeamDetail)
def get_team(team_id: ID, db: DB):
    return team_detail(db, team_id, members=True)


@router.patch("/{team_id}", response_model=TeamDetail)
def patch_team(team_id: ID, body: TeamPatch, db: DB):
    team = one(db, "TEAM", "Team_id", team_id, lock=True)
    data = body.model_dump(exclude_unset=True)
    count = member_count(db, team_id)
    capacity = data.get("max_members", team["max_members"])
    if capacity < count:
        conflict("max_members cannot be smaller than the current membership")
    state = data.get("team_status", team["team_status"])
    if state != "Closed":
        state = "Full" if count >= capacity else ("Forming" if state == "Full" else state)
    data["team_status"] = state
    update(db, "TEAM", "Team_id", team_id, data)
    return team_detail(db, team_id, members=True)


@router.delete("/{team_id}", response_model=Message)
def delete_team(team_id: ID, db: DB):
    one(db, "TEAM", "Team_id", team_id, lock=True)
    if member_count(db, team_id):
        conflict("Remove all members before deleting the team")
    if rows(
        db,
        "SELECT Request_id FROM REQUEST_TO_JOIN WHERE Team_id = :id AND Request_status = 'Pending' LIMIT 1",
        id=team_id,
    ):
        conflict("Resolve pending join requests before deleting the team")
    run(db, "DELETE FROM TEAM WHERE Team_id = :id", id=team_id)
    return {"message": "Team deleted"}


@router.put("/{team_id}/skills", response_model=TeamDetail)
def set_team_skills(team_id: ID, body: SkillIDs, db: DB):
    one(db, "TEAM", "Team_id", team_id, lock=True)
    replace_skills(db, "team", team_id, body.skill_ids)
    return team_detail(db, team_id, members=True)


@router.delete("/{team_id}/members/{student_id}", response_model=Student)
def leave_team(team_id: ID, student_id: ID, db: DB):
    # All membership operations lock student -> team -> request.
    student = one(db, "STUDENT", "Student_id", student_id, lock=True)
    team = one(db, "TEAM", "Team_id", team_id, lock=True)
    if student["team_id"] != team_id:
        conflict("This student is not a member of this team")
    remove_member(db, student, team)
    return student_detail(db, student_id)
