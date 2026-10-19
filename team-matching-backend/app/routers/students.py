from fastapi import APIRouter, Query

from app.db import DB, conflict, insert, one, rows, run, update
from app.schemas import ID, Student, StudentCreate, StudentPatch, SkillIDs, Match, Message
from app.services import replace_skills, student_detail

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("", response_model=list[Student])
def list_students(
    db: DB,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=150),
    availability: str | None = Query(None, pattern="^(Available|In Team|Busy)$"),
):
    found = rows(
        db,
        "SELECT Student_id FROM STUDENT WHERE "
        "(:search IS NULL OR Student_name LIKE :term OR email LIKE :term) "
        "AND (:availability IS NULL OR Availability_Status = :availability) "
        "ORDER BY Student_id LIMIT :limit OFFSET :offset",
        search=search,
        term=f"%{search or ''}%",
        availability=availability,
        limit=limit,
        offset=offset,
    )
    return [student_detail(db, s["student_id"]) for s in found]


@router.post("", response_model=Student, status_code=201)
def create_student(body: StudentCreate, db: DB):
    return student_detail(db, insert(db, "STUDENT", body.model_dump()))


@router.get("/{student_id}", response_model=Student)
def get_student(student_id: ID, db: DB):
    return student_detail(db, student_id)


@router.patch("/{student_id}", response_model=Student)
def patch_student(student_id: ID, body: StudentPatch, db: DB):
    student = one(db, "STUDENT", "Student_id", student_id, lock=True)
    data = body.model_dump(exclude_unset=True)
    if "availability_status" in data and student["team_id"] is not None:
        conflict("Remove the student from their team before changing availability")
    update(db, "STUDENT", "Student_id", student_id, data)
    return student_detail(db, student_id)


@router.delete("/{student_id}", response_model=Message)
def delete_student(student_id: ID, db: DB):
    student = one(db, "STUDENT", "Student_id", student_id, lock=True)
    if student["team_id"] is not None:
        conflict("Remove the student from their team before deleting them")
    if rows(db, "SELECT Project_id FROM PROJECT WHERE Created_by_student_id = :id LIMIT 1", id=student_id):
        conflict("Transfer or delete this student's proposed projects first")
    run(db, "DELETE FROM STUDENT WHERE Student_id = :id", id=student_id)
    return {"message": "Student deleted"}


@router.put("/{student_id}/skills", response_model=Student)
def set_student_skills(student_id: ID, body: SkillIDs, db: DB):
    one(db, "STUDENT", "Student_id", student_id, lock=True)
    replace_skills(db, "student", student_id, body.skill_ids)
    return student_detail(db, student_id)


@router.get("/{student_id}/matches", response_model=list[Match], tags=["Matching"])
def matches(
    student_id: ID,
    db: DB,
    available_only: bool = True,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    student = one(db, "STUDENT", "Student_id", student_id)
    found = rows(
        db,
        "SELECT m.*, t.Team_name, t.Project_id, t.team_status, p.Status AS project_status, "
        "GREATEST(0, t.max_members - (SELECT COUNT(*) FROM STUDENT s WHERE s.Team_id = t.Team_id)) AS open_seats "
        "FROM v_skill_match_summary m JOIN TEAM t USING (Team_id) JOIN PROJECT p USING (Project_id) "
        "WHERE m.Student_id = :id AND (:available = 0 OR (t.team_status IN ('Forming', 'Active') "
        "AND p.Status <> 'Closed' AND (SELECT COUNT(*) FROM STUDENT s WHERE s.Team_id = t.Team_id) < t.max_members)) "
        "ORDER BY m.match_percent DESC, t.Team_id LIMIT :limit OFFSET :offset",
        id=student_id,
        available=available_only,
        limit=limit,
        offset=offset,
    )
    for match in found:
        pending = rows(
            db,
            "SELECT Request_id FROM REQUEST_TO_JOIN WHERE Student_id = :student "
            "AND Team_id = :team AND Request_status = 'Pending' LIMIT 1",
            student=student_id,
            team=match["team_id"],
        )
        match["can_request"] = (
            student["team_id"] is None
            and student["availability_status"] == "Available"
            and match["open_seats"] > 0
            and match["team_status"] in ("Forming", "Active")
            and match["project_status"] != "Closed"
            and not pending
        )
        match["skills"] = rows(
            db,
            "SELECT required_skill, status FROM v_skill_match_detail "
            "WHERE Student_id = :student AND Team_id = :team ORDER BY required_skill",
            student=student_id,
            team=match["team_id"],
        )
    return found
