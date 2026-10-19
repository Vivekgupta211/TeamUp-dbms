from app.db import conflict, one, rows, run


def skills(db, kind, entity_id):
    table, key = ("STUDENT_SKILL", "Student_id") if kind == "student" else ("TEAM_SKILL", "Team_id")
    return rows(
        db,
        f"SELECT s.* FROM SKILL s JOIN {table} x USING (Skill_id) WHERE x.{key} = :id ORDER BY s.Skill_name",
        id=entity_id,
    )


def student_detail(db, student_id):
    student = one(db, "STUDENT", "Student_id", student_id)
    student["skills"] = skills(db, "student", student_id)
    return student


def member_count(db, team_id):
    return rows(db, "SELECT COUNT(*) AS n FROM STUDENT WHERE Team_id = :id", id=team_id)[0]["n"]


def team_detail(db, team_id, members=False):
    team = one(db, "TEAM", "Team_id", team_id)
    team["member_count"] = member_count(db, team_id)
    team["open_seats"] = max(0, team["max_members"] - team["member_count"])
    team["skills"] = skills(db, "team", team_id)
    if members:
        team["members"] = [
            student_detail(db, s["student_id"])
            for s in rows(db, "SELECT Student_id FROM STUDENT WHERE Team_id = :id ORDER BY Student_id", id=team_id)
        ]
    return team


def replace_skills(db, kind, entity_id, skill_ids):
    table, key = ("STUDENT_SKILL", "Student_id") if kind == "student" else ("TEAM_SKILL", "Team_id")
    # Lock IDs in a consistent order so catalog deletion cannot race validation.
    for skill_id in sorted(skill_ids):
        one(db, "SKILL", "Skill_id", skill_id, lock=True)
    run(db, f"DELETE FROM {table} WHERE {key} = :id", id=entity_id)
    for skill_id in skill_ids:
        run(db, f"INSERT INTO {table} ({key}, Skill_id) VALUES (:id, :skill)", id=entity_id, skill=skill_id)


def accepting_team(db, team):
    project = one(db, "PROJECT", "Project_id", team["project_id"], lock=True)
    if project["status"] == "Closed":
        conflict("This project is closed")
    if team["team_status"] not in ("Forming", "Active"):
        conflict("This team is not accepting members")
    if member_count(db, team["team_id"]) >= team["max_members"]:
        conflict("Team is already at capacity")


def remove_member(db, student, team):
    # The existing unapproval trigger releases membership and reopens Full teams.
    run(
        db,
        "UPDATE REQUEST_TO_JOIN SET Request_status = 'Rejected' "
        "WHERE Student_id = :student AND Team_id = :team AND Request_status = 'Approved'",
        student=student["student_id"],
        team=team["team_id"],
    )
    # Also supports memberships created directly by an existing SQL client.
    run(
        db,
        "UPDATE STUDENT SET Team_id = NULL, Availability_Status = 'Available' WHERE Student_id = :id",
        id=student["student_id"],
    )
    run(db, "UPDATE TEAM SET team_status = 'Forming' WHERE Team_id = :id AND team_status = 'Full'", id=team["team_id"])
