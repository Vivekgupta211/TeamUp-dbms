# Review of the supplied database

The SQL is a MySQL implementation of the ER diagram, with additional project-origin and team-state fields. The backend keeps it unchanged in `database/original.sql`.

| Diagram concept | SQL implementation |
| --- | --- |
| Student attributes | `STUDENT` |
| Multivalued student skills | `SKILL` + `STUDENT_SKILL` |
| Student belongs to zero or one team | Nullable `STUDENT.Team_id` foreign key |
| Project has many teams | `TEAM.Project_id` foreign key |
| Required skills | `TEAM_SKILL` |
| Requests with ID, date, status | `REQUEST_TO_JOIN` |
| Skill recommendations | `v_skill_match_detail`, `v_skill_match_summary` |

## Existing rules retained

- Student year is 1–6 and team capacity is 1–20.
- Student emails and skill names are unique.
- Official projects have no student creator; student-proposed projects require one.
- Request triggers reject duplicate pending requests.
- Approvals invoke `sp_apply_approval`, assign the student to the team, set `In Team`, and mark capacity reached as `Full`.
- Changing an approved request to another status removes membership and reopens a full team.
- Teams with no required skills receive a 100% match score.

## Gaps handled by the API

1. **Destructive import:** the SQL starts with `DROP DATABASE`. The Python importer skips database-selection/destruction statements and refuses a nonempty target. Never import the original file into a database you need to preserve.
2. **Concurrency:** checking counts inside a trigger is insufficient for all concurrent API workflows. The API locks the student then team during request creation/approval/removal and runs the operation in one transaction. READ COMMITTED ensures capacity checks observe the latest committed membership after obtaining the lock. Deadlocks/timeouts return a retryable 409.
3. **Direct membership writes:** SQL permits manually editing `STUDENT.Team_id` without all approval checks. The API excludes that field from profile edits and routes membership through join requests.
4. **Busy students, closed teams/projects:** extra API checks block requests/approvals when the student or destination is unavailable.
5. **Stale requests:** after approval, other pending requests for that student are rejected atomically.
6. **Capacity edits:** the API prevents reducing capacity below member count and recalculates Full/Forming.
7. **Cascading deletion:** deleting a team directly in SQL can leave `Availability_Status='In Team'` after the foreign key clears `Team_id`. The API requires removing members first. It also blocks project deletion until teams are deleted.
8. **Approved-request history:** the original unapproval trigger treats changing an approved request as removing membership. The API makes decisions final and uses a dedicated leave endpoint. Leaving records the prior approval as `Rejected`; the SQL has no separate `Left` or `Withdrawn` value.
9. **Team minimum size:** the diagram suggests at least one member per team, but SQL allows an empty team and includes empty examples. The API follows SQL so a team can be created before recruiting.
10. **Identity:** no password, user account, team owner, or admin-role tables exist. The backend provides optional shared-key protection and documents its classroom scope. It does not infer ownership from a supplied student ID.

The sample data intentionally includes a pending request for the already-full Solo Squad. Listing it is supported; trying to approve it returns 409. These API safeguards apply to writes through this backend; external SQL clients can still bypass them. No extra migrations are required.
