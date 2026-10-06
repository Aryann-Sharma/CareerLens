# Testing guide

Run commands from the repository root with the virtual environment activated.

## Install test dependencies

```text
python -m pip install -r backend/requirements-dev.txt
python -m playwright install chromium
```

On Linux CI runners, use `python -m playwright install --with-deps chromium` to install browser system dependencies as well.

## Local checks

```text
python -m pip check
python -m pytest backend/tests -q
python -m pytest e2e --browser chromium --tracing=retain-on-failure -q
python -m compileall -q backend e2e
node --check frontend/script.js
```

Node.js is needed only for the JavaScript syntax check. The application itself does not require a Node.js server or frontend build step.

The backend fixtures create an isolated in-memory SQLite database. Migration tests use temporary files. The PostgreSQL integration test is skipped unless explicitly enabled.

The browser fixture applies migrations to a temporary SQLite database and starts the real application on an available loopback port. Each test gets a fresh browser context, and the server is stopped after the suite. Tests fail on uncaught browser errors. Playwright writes retained failure traces under `test-results/`.

## Feature coverage

| Feature | Checks |
| --- | --- |
| Extraction | Every supported skill and alias, case, duplicates, punctuation, overlapping names, word boundaries, repeated input |
| Scoring | Partial and full matches, empty profiles, unknown skills, rounding, preserved ordering |
| Validation | Missing and extra fields, incorrect types, blank descriptions, input limits |
| Accounts | Registration, duplicate email, password validation and hashing, login errors, session restoration, logout |
| Sessions | Invalid and expired tokens, deleted users, production cookie flags |
| Privacy | Ownership checks, foreign IDs, legacy unowned records, cleared drafts, ignored responses after logout |
| History | Persistence, newest-first ordering, pagination, previews, complete details |
| Browser recovery | Failed analysis requests and retries, unavailable history, missing details, expired sessions |
| Interface | Example input, score and skill displays, keyboard dismissal, dialog padding, mobile long content, literal text rendering |
| Database | Migrations, schema consistency, write rollback, uniqueness, foreign keys, PostgreSQL JSONB |
| Operations | Liveness, database readiness, missing schema, production configuration |

## PostgreSQL checks

Use a disposable database. The integration and browser suites create accounts and analyses; never point them at development data you need to keep or a production database.

In PowerShell, set the test URL and enable the integration test:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://test_user:test_password@127.0.0.1:5432/careerlens_test'
$env:ENVIRONMENT = 'testing'
$env:RUN_POSTGRES_TESTS = '1'
python -m alembic upgrade head
python -m alembic check
python -m pytest backend/tests -q
$env:E2E_DATABASE_URL = $env:DATABASE_URL
python -m pytest e2e --browser chromium --tracing=retain-on-failure -q
```

The integration test checks the real PostgreSQL driver, JSONB fields, indexes, ownership, UTC dates, and the account-to-analysis flow. Most other backend tests still use isolated SQLite fixtures. Setting `E2E_DATABASE_URL` runs the complete browser suite against PostgreSQL. Browser test accounts remain in that disposable database after the run.

Remove the overrides when finished:

```powershell
Remove-Item Env:DATABASE_URL, Env:ENVIRONMENT, Env:RUN_POSTGRES_TESTS, Env:E2E_DATABASE_URL
```

For a fresh SQLite schema consistency check, set `DATABASE_URL` to an unused temporary database path, then run `python -m alembic upgrade head` and `python -m alembic check`.

## Containers

With Docker and the Compose plugin installed, configure `.env.docker` as described in the [deployment guide](deployment.md), then run:

```text
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up --build
```

Check `/health/ready` and complete registration, analysis, history, logout, and login in the browser. A passing Python suite does not verify the container image, networking, or HTTPS proxy configuration.
