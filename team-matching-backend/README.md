# Team Matching System — Python backend

A FastAPI + MySQL backend built around the supplied `dbms_project.sql` and ER diagram. It preserves the original tables, stored procedure, triggers, views, and sample data. API JSON uses **snake_case**, even though the SQL uses mixed-case column names.

Includes student/project/team/skill CRUD, skill assignment, join requests, approvals and rejection, leaving teams, ranked skill matching, dashboard counts, validation, CORS, automatic API docs, Docker setup, and real MySQL integration tests.

## Start with Docker

Install Docker Desktop and start it, then run from this folder:

```sh
docker compose up -d db
docker compose --profile setup run --rm init
docker compose up -d --build api
```

The `init` command is only for the first setup. It refuses to change a nonempty database. For subsequent runs use `docker compose up -d`. The database volume keeps your data between restarts.

- API: http://localhost:8000/api
- Interactive docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc
- Health: http://localhost:8000/health
- MySQL from the host: port **3307**, database `team_matching_system`, user `team_app`, password `team_dev_password`.

`docker compose stop` stops the services without removing data. The Docker setup uses MySQL 8.4. The local verification run used MySQL 9.2; see [verification](docs/VERIFICATION.md).

## Start with Python and an existing MySQL server

Use Python **3.11+** and MySQL **8.0.16+** (MySQL 8.4 recommended). On Windows, use `py` instead of `python3` and activate with `.venv\Scripts\activate`.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your MySQL host, port, username, password, and database name. To create a dedicated local database/user, run the following as your MySQL administrator (replace the example password if desired):

```sql
CREATE DATABASE IF NOT EXISTS team_matching_system CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'team_app'@'localhost' IDENTIFIED BY 'team_dev_password';
GRANT ALL PRIVILEGES ON team_matching_system.* TO 'team_app'@'localhost';
```

For a **new empty** database:

```sh
python -m scripts.init_db
```

If your teammate already imported the supplied SQL, **skip initialization** and point `.env` at that database. No schema changes are required. The setup user needs privileges to create tables, routines, triggers, and views. On a server with binary logging enabled, ask your database administrator to run the import or enable `log_bin_trust_function_creators` for local development; otherwise MySQL may return error 1419 when creating triggers. The Docker database is configured for this.

Start the API:

```sh
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://localhost:8000/docs and try the endpoints. With the original seed, Priya (`student_id=2`) is available, team `3` has no skill requirements, and team `4` is already full.

## Frontend handoff

Send your teammates the project ZIP, [frontend guide](docs/FRONTEND_HANDOFF.md), and [JavaScript API client](docs/api-client.js). They can build a React/Vue/plain JavaScript frontend independently. They need the backend running and must use `http://localhost:8000/api` as their base URL.

The frontend runs on port 5173 or 3000 by default. Add its exact origin to `CORS_ORIGINS` in `.env` for other ports. CORS configuration is a JSON array. If teammates use another computer, run Uvicorn with `--host 0.0.0.0`, give them your machine's LAN address, and add their frontend origin. Docker binds the API to localhost by default; change its published host address in `compose.yaml` if LAN access is needed.

This is a classroom demo backend: the supplied database has no password accounts or team-owner roles. An optional shared `API_KEY` enables `X-API-Key` checks for all `/api` routes; it is not per-student authentication. A student selector in the frontend selects a profile, not a signed-in identity. Add authentication and ownership checks before using it as a public multi-user service.

## API overview

All endpoints below start with `/api`. Lists return JSON arrays and support `limit` (1–100, default 50) and `offset` (default 0).

| Resource | Endpoints |
| --- | --- |
| Students | `GET/POST /students`; `GET/PATCH/DELETE /students/{id}` |
| Student skills | `PUT /students/{id}/skills` |
| Recommendations | `GET /students/{id}/matches?available_only=true` |
| Projects | `GET/POST /projects`; `GET/PATCH/DELETE /projects/{id}` |
| Teams | `GET/POST /teams`; `GET/PATCH/DELETE /teams/{id}` |
| Required skills | `PUT /teams/{id}/skills` |
| Leave/remove member | `DELETE /teams/{team_id}/members/{student_id}` |
| Skills catalog | `GET/POST /skills`; `PATCH/DELETE /skills/{id}` |
| Join requests | `GET/POST /requests`; `GET/PATCH/DELETE /requests/{id}` |
| Dashboard | `GET /dashboard` |

Full request/response schemas are in `/docs` and `/openapi.json`. The exported [OpenAPI contract](docs/openapi.json) can also be imported into Postman. Refresh it after API changes with `python -m scripts.export_openapi`. More details, sample calls, state rules, and filters are in the frontend guide. Database observations are recorded in [schema review](docs/SCHEMA_REVIEW.md).

## Test

```sh
pip install -r requirements-dev.txt
python -m pytest -q
ruff check app scripts tests
```

Without test database settings, validation tests run and integration tests are explicitly skipped. To run all tests against real MySQL, supply a **test administrator** account that can create/drop test databases and create routines/triggers:

```sh
TEST_DB_HOST=127.0.0.1 TEST_DB_PORT=3306 TEST_DB_USER=root TEST_DB_PASSWORD=your_password python -m pytest -q
```

With the Docker database use port `3307` and root password `local_root_password`. Every integration test creates a random `team_matching_test_*` database, imports the original SQL, and drops only that temporary database afterward. Tests cover capacity races, duplicate requests, membership transitions, trigger effects, rollback, schema validation, CORS, optional API keys, and safe initialization.

`requirements-lock.txt` records the exact dependency versions used in verification, including test tools. To reproduce them use `pip install -r requirements-lock.txt`.

To recreate the source handoff ZIP after making changes, run `python -m scripts.package`. It excludes local credentials, virtual environments, and caches.

## Files

```text
app/config.py          Environment configuration
app/db.py              SQLAlchemy connection pool and transaction helpers
app/schemas.py         Validated input and typed response models
app/services.py        Shared membership, skill, and detail operations
app/routers/           API endpoints by resource
app/main.py            FastAPI, CORS, error handlers, dashboard, health
database/original.sql  Unchanged SQL received from your teammate
scripts/init_db.py     Non-destructive SQL importer
docs/                  Frontend handoff, API client, schema review, verification
tests/                 Validation and real MySQL integration tests
```
