from concurrent.futures import ThreadPoolExecutor

from app.main import settings
from scripts.init_db import initialize


def post(client, path, body):
    response = client.post("/api" + path, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def student(client, name="New Student"):
    return post(client, "/students", {"student_name": name, "email": name.replace(" ", "") + "@example.com"})


def team(client, capacity=2):
    return post(client, "/teams", {"team_name": "New Team", "project_id": 3, "max_members": capacity})


def request(client, s, t):
    return post(client, "/requests", {"student_id": s["student_id"], "team_id": t["team_id"]})


def decide(client, r, status="Approved"):
    return client.patch(f"/api/requests/{r['request_id']}", json={"request_status": status})


def test_seed_and_docs(client):
    assert client.get("/health").json()["status"] == "ok"
    assert len(client.get("/api/students").json()) == 4
    assert client.get("/api/teams/4").json()["team_status"] == "Full"
    assert client.get("/api/dashboard").json()["projects"] == 3
    assert client.get("/docs").status_code == 200
    assert "/api/requests/{request_id}" in client.get("/openapi.json").json()["paths"]


def test_student_crud_and_conflicts(client):
    s = student(client)
    path = f"/api/students/{s['student_id']}"
    assert client.patch(path, json={"current_year": 2, "branch": "CSE"}).json()["branch"] == "CSE"
    assert client.patch(path, json={"branch": None}).json()["branch"] is None
    assert client.post("/api/students", json={"student_name": "Duplicate", "email": s["email"]}).status_code == 409
    assert client.patch(path, json={"team_id": 1}).status_code == 422
    assert client.get("/api/students?limit=101").status_code == 422
    assert client.delete(path).status_code == 200
    assert client.get(path).status_code == 404


def test_skill_assignment_and_rollback(client):
    path = "/api/students/2/skills"
    assert client.put(path, json={"skill_ids": [1, 6]}).status_code == 200
    assert client.put(path, json={"skill_ids": [1, 9999]}).status_code == 404
    assert [s["skill_id"] for s in client.get("/api/students/2").json()["skills"]] == [1, 6]
    assert client.put(path, json={"skill_ids": []}).json()["skills"] == []
    skill = post(client, "/skills", {"skill_name": "Testing"})
    assert client.patch(f"/api/skills/{skill['skill_id']}", json={"skill_name": "QA"}).json()["skill_name"] == "QA"
    assert client.delete(f"/api/skills/{skill['skill_id']}").status_code == 200


def test_matching_includes_empty_skill_teams(client):
    matches = client.get("/api/students/2/matches").json()
    ace = next(m for m in matches if m["team_id"] == 3)
    assert ace["match_percent"] == 100
    assert ace["total_required"] == 0
    assert ace["can_request"] is True
    assert not any(m["team_id"] == 4 for m in matches)
    all_teams = client.get("/api/students/2/matches?available_only=false").json()
    assert next(m for m in all_teams if m["team_id"] == 4)["can_request"] is False


def test_approval_capacity_and_leave(client):
    s, t = student(client), team(client, 1)
    r = request(client, s, t)
    assert decide(client, r).status_code == 200
    enrolled = client.get(f"/api/students/{s['student_id']}").json()
    assert enrolled["team_id"] == t["team_id"]
    assert enrolled["availability_status"] == "In Team"
    assert client.get(f"/api/teams/{t['team_id']}").json()["team_status"] == "Full"
    assert decide(client, r).status_code == 409
    assert client.patch(f"/api/students/{s['student_id']}", json={"availability_status": "Busy"}).status_code == 409
    assert client.delete(f"/api/teams/{t['team_id']}").status_code == 409
    assert client.delete(f"/api/teams/{t['team_id']}/members/{s['student_id']}").json()["team_id"] is None
    assert client.get(f"/api/teams/{t['team_id']}").json()["team_status"] == "Forming"
    assert client.get(f"/api/requests/{r['request_id']}").json()["request_status"] == "Rejected"


def test_pending_duplicate_and_withdrawal(client):
    s, t = student(client), team(client)
    r = request(client, s, t)
    assert (
        client.post("/api/requests", json={"student_id": s["student_id"], "team_id": t["team_id"]}).status_code == 409
    )
    assert client.delete(f"/api/teams/{t['team_id']}").status_code == 409
    assert client.delete(f"/api/requests/{r['request_id']}").status_code == 200
    assert client.delete(f"/api/teams/{t['team_id']}").status_code == 200


def test_closed_busy_and_rejection_rules(client):
    s, t = student(client), team(client)
    r = request(client, s, t)
    client.patch(f"/api/teams/{t['team_id']}", json={"team_status": "Closed"})
    assert decide(client, r).status_code == 409
    assert decide(client, r, "Rejected").status_code == 200
    assert client.get(f"/api/students/{s['student_id']}").json()["team_id"] is None
    client.patch(f"/api/teams/{t['team_id']}", json={"team_status": "Forming"})
    client.patch(f"/api/students/{s['student_id']}", json={"availability_status": "Busy"})
    assert (
        client.post("/api/requests", json={"student_id": s["student_id"], "team_id": t["team_id"]}).status_code == 409
    )


def test_approval_rejects_other_pending_requests(client):
    s, t1, t2 = student(client), team(client), team(client)
    r1, r2 = request(client, s, t1), request(client, s, t2)
    assert decide(client, r1).status_code == 200
    assert client.get(f"/api/requests/{r2['request_id']}").json()["request_status"] == "Rejected"


def test_project_consistency_and_deletion(client):
    assert client.post("/api/projects", json={"project_name": "No creator"}).status_code == 422
    p = post(client, "/projects", {"project_name": "Student idea", "created_by_student_id": 2})
    path = f"/api/projects/{p['project_id']}"
    assert client.patch(path, json={"is_official": True}).status_code == 409
    assert client.patch(path, json={"is_official": True, "created_by_student_id": None}).json()["is_official"] is True
    assert client.delete(path).status_code == 200
    assert client.delete("/api/projects/3").status_code == 409
    assert client.delete("/api/students/2").status_code == 409
    assert client.patch("/api/projects/3", json={"status": "Closed"}).status_code == 200
    assert client.post("/api/teams", json={"team_name": "Closed", "project_id": 3}).status_code == 409


def test_capacity_recalculation(client):
    s, t = student(client), team(client, 1)
    assert decide(client, request(client, s, t)).status_code == 200
    path = f"/api/teams/{t['team_id']}"
    assert client.patch(path, json={"max_members": 2}).json()["team_status"] == "Forming"
    s2 = student(client, "Second Student")
    assert decide(client, request(client, s2, t)).status_code == 200
    assert client.patch(path, json={"max_members": 1}).status_code == 409


def test_two_students_compete_for_last_seat(client):
    t = team(client, 1)
    r1 = request(client, student(client, "Student One"), t)
    r2 = request(client, student(client, "Student Two"), t)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda r: decide(client, r).status_code, [r1, r2]))
    assert sorted(results) == [200, 409]
    assert client.get(f"/api/teams/{t['team_id']}").json()["member_count"] == 1


def test_student_competing_approvals(client):
    s, t1, t2 = student(client), team(client), team(client)
    r1, r2 = request(client, s, t1), request(client, s, t2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda r: decide(client, r).status_code, [r1, r2]))
    assert sorted(results) == [200, 409]
    assert sum(client.get(f"/api/teams/{t['team_id']}").json()["member_count"] for t in [t1, t2]) == 1


def test_optional_key_and_cors(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    assert client.get("/api/students").status_code == 401
    assert client.get("/api/students", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/students", headers={"X-API-Key": "test-secret"}).status_code == 200
    response = client.options(
        "/api/students",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.options(
        "/api/students", headers={"Origin": "https://unknown.example.com", "Access-Control-Request-Method": "GET"}
    )
    assert "access-control-allow-origin" not in denied.headers


def test_initializer_never_overwrites(client):
    import pytest

    with pytest.raises(SystemExit, match="not empty"):
        initialize()
    assert len(client.get("/api/students").json()) == 4
