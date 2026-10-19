from fastapi import APIRouter, Query

from app.db import DB, insert, one, rows, run, update
from app.schemas import ID, Message, Skill, SkillCreate

router = APIRouter(prefix="/skills", tags=["Skills"])


@router.get("", response_model=list[Skill])
def list_skills(db: DB, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return rows(db, "SELECT * FROM SKILL ORDER BY Skill_name LIMIT :limit OFFSET :offset", limit=limit, offset=offset)


@router.post("", response_model=Skill, status_code=201)
def create_skill(body: SkillCreate, db: DB):
    return one(db, "SKILL", "Skill_id", insert(db, "SKILL", body.model_dump()))


@router.patch("/{skill_id}", response_model=Skill)
def rename_skill(skill_id: ID, body: SkillCreate, db: DB):
    one(db, "SKILL", "Skill_id", skill_id, lock=True)
    update(db, "SKILL", "Skill_id", skill_id, body.model_dump())
    return one(db, "SKILL", "Skill_id", skill_id)


@router.delete("/{skill_id}", response_model=Message)
def delete_skill(skill_id: ID, db: DB):
    one(db, "SKILL", "Skill_id", skill_id, lock=True)
    run(db, "DELETE FROM SKILL WHERE Skill_id = :id", id=skill_id)
    return {"message": "Skill deleted; removed from student and team skill lists"}
