import pytest
from pydantic import ValidationError

from app.schemas import ProjectCreate, SkillIDs, StudentCreate, StudentPatch, TeamCreate
from scripts.init_db import statements


@pytest.mark.parametrize(
    "data",
    [
        {"student_name": "", "email": "a@b.com"},
        {"student_name": "Alice", "email": "invalid"},
        {"student_name": "Alice", "email": "a@b.com", "current_year": 7},
        {"student_name": "Alice", "email": "a@b.com", "team_id": 1},
    ],
)
def test_invalid_students(data):
    with pytest.raises(ValidationError):
        StudentCreate(**data)


@pytest.mark.parametrize("data", [{}, {"student_name": None}, {"availability_status": "In Team"}])
def test_invalid_patches(data):
    with pytest.raises(ValidationError):
        StudentPatch(**data)


def test_nullable_patch_and_trim():
    assert StudentPatch(branch=None).model_dump(exclude_unset=True) == {"branch": None}
    assert StudentCreate(student_name=" Alice ", email="alice@example.com").student_name == "Alice"


def test_project_creator_consistency():
    with pytest.raises(ValidationError):
        ProjectCreate(project_name="Missing creator")
    with pytest.raises(ValidationError):
        ProjectCreate(project_name="Official", is_official=True, created_by_student_id=1)


def test_duplicate_skills_and_capacity():
    with pytest.raises(ValidationError):
        SkillIDs(skill_ids=[1, 1])
    with pytest.raises(ValidationError):
        TeamCreate(team_name="Too big", project_id=1, max_members=21)


def test_delimiter_parser():
    source = "CREATE TABLE X (id INT);\nDELIMITER $$\nCREATE PROCEDURE p()\nBEGIN\nSELECT 1;\nEND$$\nDELIMITER ;\nSELECT 2; -- comment"
    parsed = list(statements(source))
    assert len(parsed) == 3
    assert "SELECT 1;" in parsed[1]
    assert parsed[-1] == "SELECT 2"
