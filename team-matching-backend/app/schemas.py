from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

ID = Annotated[int, Field(gt=0)]
Name = Annotated[str, Field(min_length=1, max_length=150)]
SkillName = Annotated[str, Field(min_length=1, max_length=100)]
Year = Annotated[int, Field(ge=1, le=6)]
Capacity = Annotated[int, Field(ge=1, le=20)]
Availability = Literal["Available", "Busy"]
ProjectStatus = Literal["Open", "In Progress", "Closed"]
TeamStatus = Literal["Forming", "Active", "Closed"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Patch(Input):
    @model_validator(mode="after")
    def check_patch(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        nullable = {"branch", "current_year", "description", "category", "timeline", "created_by_student_id"}
        for name in self.model_fields_set:
            if getattr(self, name) is None and name not in nullable:
                raise ValueError(f"{name} cannot be null")
        return self


class SkillIDs(Input):
    skill_ids: list[ID] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_ids(self):
        if len(self.skill_ids) != len(set(self.skill_ids)):
            raise ValueError("skill_ids must not contain duplicates")
        return self


class StudentCreate(Input):
    student_name: Name
    email: Annotated[EmailStr, Field(max_length=150)]
    branch: Annotated[str, Field(max_length=100)] | None = None
    current_year: Year | None = None
    availability_status: Availability = "Available"


class StudentPatch(Patch):
    student_name: Name | None = None
    email: Annotated[EmailStr, Field(max_length=150)] | None = None
    branch: Annotated[str, Field(max_length=100)] | None = None
    current_year: Year | None = None
    availability_status: Availability | None = None


class SkillCreate(Input):
    skill_name: SkillName


class ProjectCreate(Input):
    project_name: Name
    description: Annotated[str, Field(max_length=15000)] | None = None
    category: Annotated[str, Field(max_length=100)] | None = None
    status: ProjectStatus = "Open"
    timeline: Annotated[str, Field(max_length=100)] | None = None
    is_official: bool = False
    created_by_student_id: ID | None = None

    @model_validator(mode="after")
    def creator_rule(self):
        if self.is_official == (self.created_by_student_id is not None):
            raise ValueError("Official projects need a null creator; student projects need a creator ID")
        return self


class ProjectPatch(Patch):
    project_name: Name | None = None
    description: Annotated[str, Field(max_length=15000)] | None = None
    category: Annotated[str, Field(max_length=100)] | None = None
    status: ProjectStatus | None = None
    timeline: Annotated[str, Field(max_length=100)] | None = None
    is_official: bool | None = None
    created_by_student_id: ID | None = None


class TeamCreate(Input):
    team_name: Name
    project_id: ID
    max_members: Capacity = 5
    team_status: TeamStatus = "Forming"


class TeamPatch(Patch):
    team_name: Name | None = None
    max_members: Capacity | None = None
    team_status: TeamStatus | None = None


class RequestCreate(Input):
    student_id: ID
    team_id: ID


class RequestDecision(Input):
    request_status: Literal["Approved", "Rejected"]


class Skill(BaseModel):
    skill_id: int
    skill_name: str


class Student(BaseModel):
    student_id: int
    student_name: str
    email: str
    branch: str | None
    current_year: int | None
    availability_status: Literal["Available", "Busy", "In Team"]
    team_id: int | None
    skills: list[Skill]


class Project(BaseModel):
    project_id: int
    project_name: str
    description: str | None
    category: str | None
    status: ProjectStatus
    timeline: str | None
    is_official: bool
    created_by_student_id: int | None


class Team(BaseModel):
    team_id: int
    team_name: str
    team_status: Literal["Forming", "Active", "Full", "Closed"]
    max_members: int
    project_id: int
    member_count: int
    open_seats: int
    skills: list[Skill]


class TeamDetail(Team):
    members: list[Student]


class JoinRequest(BaseModel):
    request_id: int
    student_id: int
    team_id: int
    request_status: Literal["Pending", "Approved", "Rejected"]
    request_date: date | None


class Match(BaseModel):
    student_id: int
    team_id: int
    team_name: str
    project_id: int
    total_required: int
    matched: int
    match_percent: float
    open_seats: int
    can_request: bool
    skills: list[dict[str, str | None]]


class Message(BaseModel):
    message: str


class FieldIssue(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    message: str
    details: list[FieldIssue] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Dashboard(BaseModel):
    students: int
    teams: int
    projects: int
    available_students: int
    pending_requests: int


class Health(BaseModel):
    status: str
    database: str
