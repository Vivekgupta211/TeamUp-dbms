# Verification

Verified on **14 October 2026** using Python 3.13.7 and an isolated local MySQL 9.2.0 instance. No existing database was modified. Exact installed Python packages are recorded in `requirements-lock.txt`.

## Results

- **25 tests passed** with all integration tests enabled against real MySQL, including the original stored procedure and triggers.
- Concurrent approvals for a one-seat team produced one successful approval and one 409 conflict; membership stayed within capacity.
- Concurrent approvals for the same student into different teams produced one successful membership and one conflict.
- Tested entity validation, CRUD, duplicate email/request rejection, skill replacement and rollback, skill matching, capacity edits, leaving teams, closed destinations, safe deletions, optional API keys, CORS, and refusal to reinitialize a nonempty database.
- Started Uvicorn and exercised actual HTTP requests with the bundled JavaScript client: health/docs, missing-key rejection, profile reads, matching, creating a student, assigning skills, joining, approving, conflict handling, leaving, and deleting.
- Successfully imported the SQL with a non-root database user with database-scoped privileges and `log_bin_trust_function_creators=1` (the same development setting used in Compose).
- Ruff lint and formatting checks passed. Python dependency consistency checks passed. JavaScript syntax checks passed.
- `docker compose config --quiet` passed. Docker services were **not started** because Docker Desktop's daemon was unavailable. The provided Compose configuration targets MySQL 8.4; runtime verification used the locally installed MySQL 9.2.
- Copied the supplied SQL directly into `database/original.sql` and retained it without schema edits.

The test runner emitted one upstream Starlette warning about its `httpx` test-client integration being deprecated. It did not affect the tests or API runtime.

## Reproduce the integration run

Use a disposable MySQL server or a test administrator account with permission to create/drop test databases and create triggers/routines:

```sh
pip install -r requirements-lock.txt
TEST_DB_HOST=127.0.0.1 TEST_DB_PORT=3306 TEST_DB_USER=root TEST_DB_PASSWORD=your_password python -m pytest -q
ruff check app scripts tests
ruff format --check app scripts tests
```

Each integration test uses its own random `team_matching_test_*` database and removes it afterward. Without `TEST_DB_HOST`, the integration tests are skipped explicitly; that run alone does not verify MySQL behavior.
