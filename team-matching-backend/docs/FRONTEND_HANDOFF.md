# Frontend handoff

Start the backend using the README. Open http://localhost:8000/docs for live request forms and complete response types. Base URL: **`http://localhost:8000/api`**. Requests and responses are JSON. Use `Content-Type: application/json` for request bodies. If the backend has an `API_KEY`, also send `X-API-Key`.

## Suggested screens and API calls

| Screen / action | API |
| --- | --- |
| Dashboard | `GET /dashboard` |
| Student/profile selector | `GET /students` |
| Profile page | `GET /students/{id}` |
| Create profile | `POST /students` |
| Edit profile | `PATCH /students/{id}` |
| Skill picker | `GET /skills` |
| Save profile skills | `PUT /students/{id}/skills` with `{"skill_ids":[1,6]}` |
| Project browser | `GET /projects` |
| Create student idea | `POST /projects` with a creator ID |
| Team browser | `GET /teams` or `GET /teams?project_id=3` |
| Team page, members, requirements | `GET /teams/{id}` |
| Recommended teams | `GET /students/{id}/matches` |
| Send join request | `POST /requests` with student/team IDs |
| Student's request history | `GET /requests?student_id=2` |
| Team's inbox | `GET /requests?team_id=3&status=Pending` |
| Approve/reject | `PATCH /requests/{id}` with `request_status` |
| Withdraw pending request | `DELETE /requests/{id}` |
| Leave/remove member | `DELETE /teams/{team_id}/members/{student_id}` |

All table values use the spelling/capitalization from SQL: `Available`, `Busy`, `In Team`, `Open`, `In Progress`, `Closed`, `Forming`, `Active`, `Full`, `Pending`, `Approved`, `Rejected`.

## Example workflow

This works once on a fresh seeded database. Use a new student/request or remove membership before repeating it.

```sh
# View an available student and their matches.
curl http://localhost:8000/api/students/2
curl http://localhost:8000/api/students/2/matches

# Send a request. Read request_id from this response.
curl -X POST http://localhost:8000/api/requests \
  -H 'Content-Type: application/json' \
  -d '{"student_id":2,"team_id":3}'

# Substitute the returned request_id for 5.
curl -X PATCH http://localhost:8000/api/requests/5 \
  -H 'Content-Type: application/json' \
  -d '{"request_status":"Approved"}'

# Refresh team/profile/history after an approval.
curl http://localhost:8000/api/teams/3
curl http://localhost:8000/api/students/2
curl http://localhost:8000/api/requests?student_id=2
```

Create entities:

```json
// POST /students
{"student_name":"Riya","email":"riya@example.com","branch":"CSE","current_year":3}

// POST /projects — student proposal
{"project_name":"Campus Planner","description":"A campus planner","category":"Web/App","timeline":"Oct–Dec 2026","created_by_student_id":2}

// POST /projects — official project
{"project_name":"College Challenge","is_official":true,"created_by_student_id":null}

// POST /teams — an empty team, then members join through approval
{"team_name":"Builders","project_id":3,"max_members":4}

// PUT /teams/{id}/skills — replaces the entire required-skill set
{"skill_ids":[1,6]}
```

The comments above explain separate JSON bodies; do not include comments in actual JSON requests. `PUT .../skills` replaces the whole set; `[]` clears it. To rename a skill use `PATCH /skills/{id}` with `{"skill_name":"New name"}`.

Example `GET /students/2` response on a fresh database:

```json
{
  "student_id": 2,
  "student_name": "Priya Verma",
  "email": "priya245@example.com",
  "branch": "EVD",
  "current_year": 2,
  "availability_status": "Available",
  "team_id": null,
  "skills": [
    {"skill_id": 3, "skill_name": "JavaScript"},
    {"skill_id": 4, "skill_name": "React"}
  ]
}
```

Team details contain `member_count`, `open_seats`, `skills`, and `members`. Team lists omit the `members` array. Recommendations contain `match_percent`, `matched`, `total_required`, `open_seats`, `can_request`, and per-skill `Have` / `Missing` entries. For teams with no requirements, match percent is 100 and detail status is `No skills required`. Show the percentage as a recommendation, not an admission requirement: the backend permits partial skill matches.

## UI state rules

- Only students with no team and availability `Available` can send a request. Use `can_request` from recommendations to disable buttons, then handle server conflicts in case state changes.
- A student can have pending requests to different teams, but only one pending request per student/team pair.
- An approval atomically adds membership and changes availability to `In Team`. Other pending requests for that student become `Rejected`.
- Teams/project must be open to new membership and the team must have a free seat at approval time.
- Only `Pending` requests can be decided or withdrawn. To leave after approval, use the team membership endpoint. That also changes the old approved request to `Rejected`, consistent with the supplied status choices.
- The server calculates `Full`; do not submit `Full` or `In Team` in edit forms.
- A full team reopens as `Forming` when a member leaves or capacity increases. `Closed` teams stay closed until explicitly reopened.
- A team is created empty. It does not automatically add the project creator or a team captain; those fields do not exist in the source schema.
- Remove members and resolve pending requests before deleting a team. Delete teams before deleting a project. A student who proposed a project must transfer/delete that project before deletion.
- Skill deletion removes that skill from all students and teams through SQL cascades.
- PATCH changes only provided fields. `null` clears optional text/year fields; omit required fields to leave them unchanged. Empty patches, unknown fields, and invalid IDs are rejected.

## Filters and pagination

All lists: `limit=50&offset=0`, limit at most 100; request the next page by increasing offset. Results are plain arrays. An empty array signals no results.

| List | Extra filters |
| --- | --- |
| Students | `search` (name/email), `availability` |
| Projects | `status`, `category` |
| Teams | `project_id`, `status` |
| Requests | `student_id`, `team_id`, `status` |
| Matches | `available_only=true` (default); false also shows closed/full teams |

Match results sort by percentage descending, then team ID. Entity lists sort by ID ascending except requests (newest first); skills sort by name.

## Errors

```json
{"error":{"message":"A pending request already exists for this student and team"}}
```

Validation errors include details:

```json
{"error":{"message":"Validation failed","details":[{"field":"body.email","message":"value is not a valid email address"}]}}
```

| Status | Frontend behavior |
| --- | --- |
| 200 | Successful read/update/delete |
| 201 | Successful creation |
| 401 | Shared API key missing or incorrect |
| 404 | Record missing |
| 409 | Show message and refresh related data; concurrent update conflicts may be retried |
| 422 | Show validation messages next to fields |
| 503 | Database unreachable/not initialized; show a retry state |

Copy [api-client.js](api-client.js) into your frontend to use a shared fetch wrapper. If using Vite, initialize it with `createApiClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api')`. A key shipped to a browser is shared demo access control; it is not a secret individual identity.
