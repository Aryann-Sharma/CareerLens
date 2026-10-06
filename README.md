# CareerLens

![CI](https://github.com/Aryann-Sharma/CareerLens/actions/workflows/ci.yml/badge.svg)

CareerLens compares the technical skills in a job description with a user's skills. It shows a percentage match, lists matched and missing skills, and saves each analysis to the user's private history.

The project connects a browser interface to a Python API and a relational database. The interface uses HTML, CSS, and JavaScript; the backend uses FastAPI and SQLAlchemy.

## Features

- Register, log in, and restore a session using an HTTP-only cookie.
- Paste a job description and enter a comma-separated list of skills.
- Recognize common aliases, ignore case, and remove duplicate skill mentions.
- View matched skills, missing skills, and a percentage score.
- Browse paginated history and open the full details of a saved analysis.
- Keep each user's history separate, including when switching accounts.
- Use the interface on desktop or mobile, with keyboard-accessible dialogs.
- Run locally with SQLite or use PostgreSQL with versioned Alembic migrations.

## How matching works

The extractor checks a fixed vocabulary: **Docker, FastAPI, Git, Java, JavaScript, Linux, PostgreSQL, Python, React, and SQL**. Aliases include `js`, `ecmascript`, `fast api`, `postgres`, `postgre sql`, `react.js`, and `reactjs`.

Skills appear in the order they first occur in the description. Longer aliases take precedence, so `React.js` counts as React and does not also count as JavaScript. Repeated mentions count once.

```text
score = round(matched skills / extracted skills * 100)
```

Every detected skill has equal weight. If no supported skills are found, the score is zero. Unknown user-entered skills are kept in the saved profile but cannot match skills outside the vocabulary.

The score measures coverage of detected skills. It does not measure hiring probability, experience, education, or suitability for a role. The extractor also does not distinguish required, optional, and negated mentions.

## Stack and structure

| Area | Tools |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy |
| Data | PostgreSQL, SQLite, Alembic |
| Authentication | Argon2 password hashing, signed JWT session cookies |
| Frontend | HTML, CSS, vanilla JavaScript |
| Testing | pytest, HTTPX, Playwright with Chromium |
| Packaging and checks | Docker, Docker Compose, GitHub Actions |

```text
backend/
  app/
    api/          # Routes and authentication dependencies
    core/         # Environment settings
    db/           # Database engine and sessions
    models/       # Users and saved analyses
    schemas/      # Request validation and response formats
    services/     # Matching, passwords, sessions, and storage
    main.py       # Application and static frontend routes
  migrations/     # Versioned schema changes
  tests/          # Unit, API, migration, and PostgreSQL tests
frontend/         # Browser interface
e2e/             # Browser tests against a running application
docs/            # Deployment and testing guides
```

## Run locally

Use Python 3.12. From the repository root, create a virtual environment:

```text
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

For Git Bash on Windows, use `source .venv/Scripts/activate`.

Install dependencies, apply the schema, and start the server:

```text
python -m pip install -r backend/requirements.txt
python -m alembic upgrade head
python -m uvicorn backend.app.main:app --reload
```

Open [the app](http://127.0.0.1:8000) and create an account. The [interactive API documentation](http://127.0.0.1:8000/docs) is served by the same application.

Without a `.env` file, the app uses `careerlens.db` in the working directory and a development-only signing secret. Run commands from the repository root. Local database files and environment files are ignored by Git.

### PostgreSQL and containers

To use an existing PostgreSQL database, copy `.env.example` to `.env`, set `DATABASE_URL` and `AUTH_SECRET_KEY`, then run `python -m alembic upgrade head`. The URL must use the installed driver: `postgresql+psycopg://user:password@host:5432/database`. URL-encode reserved characters in database credentials.

For a local application and PostgreSQL stack, follow the [deployment guide](docs/deployment.md). It covers Compose configuration, migrations, health checks, and production settings.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Create an account and start a session |
| POST | `/api/auth/login` | Start a session |
| POST | `/api/auth/logout` | Clear the browser's session cookie |
| GET | `/api/auth/me` | Return the signed-in user |
| POST | `/api/analyze` | Analyze and save a job description |
| GET | `/api/analyses` | List the signed-in user's history |
| GET | `/api/analyses/{id}` | Open one owned analysis |
| GET | `/health/live` | Check that the application responds |
| GET | `/health/ready` | Check the database connection and required table columns |

`/health` is an alias for `/health/live`. All analysis and history routes require authentication. A missing or foreign-owned analysis returns `404`.

Example request to `POST /api/analyze`:

```json
{
  "job_description": "We need Python, SQL, React, Git and FastAPI.",
  "user_skills": ["Python", "Java", "SQL", "Git"]
}
```

Response:

```json
{
  "extracted_skills": ["Python", "SQL", "React", "Git", "FastAPI"],
  "matched_skills": ["Python", "SQL", "Git"],
  "missing_skills": ["React", "FastAPI"],
  "match_score": 60
}
```

Descriptions must contain 1–50,000 characters after trimming. Requests accept up to 200 user skills, each at most 100 characters after trimming. Blank entries and case-insensitive duplicates are removed; an empty skill list is allowed. Unknown request fields are rejected.

History uses `page` and `page_size`, with defaults of 1 and 10. Pages range from 1 to 2,147,483,647; page size ranges from 1 to 50. The browser shows five records per page. Results are ordered newest first, with the record ID breaking timestamp ties. API timestamps include a UTC offset; the browser displays them in the user's timezone.

Registration and login accept `email` and `password`. Email addresses are normalized for case-insensitive lookup. Registration requires a password of 12–128 characters. Sessions last 60 minutes by default and use HTTP-only, SameSite=Lax cookies; production also enables Secure cookies. Logout clears the cookie, while previously issued tokens remain valid until expiry. Explicit logout clears the draft and displayed results. After a session expires, the draft is restored only when the same account signs back in.

## Tests and continuous integration

Install the development dependencies and browser:

```text
python -m pip install -r backend/requirements-dev.txt
python -m playwright install chromium
```

Run the suites:

```text
python -m pytest backend/tests -q
python -m pytest e2e --browser chromium -q
```

The [testing guide](docs/testing.md) describes feature coverage, PostgreSQL tests, and additional checks. Local browser tests use a temporary SQLite database unless `E2E_DATABASE_URL` is explicitly set. They do not use the development database.

GitHub Actions runs on pull requests and pushes to `main`. It checks dependencies, migrations, the backend suite, PostgreSQL integration, Chromium browser journeys against PostgreSQL, Python compilation, JavaScript syntax, Compose configuration, and the container build.

## Limitations and next steps

- Matching uses the ten-skill vocabulary above and does not interpret sentence meaning.
- History has no search, filtering, or deletion controls.
- Accounts have no email verification, password reset, or session revocation.
- Request throttling is not built in; a public deployment needs rate limits at the proxy or application layer.
- File uploads and document parsing are not implemented.
- Hosting and a managed production database are not configured in this repository.

The next step is deploying the existing application behind HTTPS with PostgreSQL backups and monitoring. Broader skill coverage and account-management features can follow once the deployed version has been tested.
