# CareerLens

![CI](https://github.com/Aryann-Sharma/CareerLens/actions/workflows/ci.yml/badge.svg)

CareerLens is a full-stack job-description analysis app for students and job seekers. Paste a job description, enter your current skills, and receive a clear breakdown of required, matched, and missing skills with a match score.

The current MVP has a browser interface connected to a FastAPI backend, account authentication, and private analysis history. It can extract supported skills from a job description, compare them with a user's skills, calculate a match score, save the analysis for the signed-in user, and show the result in the browser. Users can create an account, log in, restore an existing session, and log out without leaving the main page.

## How it works

1. The API identifies the user from the signed session cookie.
2. The user enters a job description and a list of their skills in the browser.
3. The frontend sends the data to `POST /api/analyze` as JSON.
4. Pydantic validates and cleans the request before it reaches the analysis logic.
5. The skill extractor searches the description using a curated list of skills and common aliases.
6. The scorer compares the extracted skills with the user's skills.
7. SQLAlchemy saves the request and result with the authenticated user's ID.
8. The API returns the extracted, matched, and missing skills with a percentage score.
9. The frontend displays the result and refreshes only that user's analysis history.

The score is calculated as:

```text
(number of matched skills / number of extracted skills) * 100
```

All supported skills currently have equal weight. If no supported skills are found in the description, the score is `0`.

## Current features

- Rule-based extraction from a curated technical-skill vocabulary
- Alias handling (for example, `js` becomes `JavaScript` and `postgres` becomes `PostgreSQL`)
- Case-insensitive matching with duplicate removal
- Transparent match score based on the percentage of required skills covered
- Responsive HTML/CSS/JavaScript frontend
- Browser registration, login, logout, and session restoration
- Clear signed-out and expired-session states
- FastAPI request validation and API documentation
- Database persistence through SQLAlchemy
- Versioned database migrations with Alembic
- PostgreSQL configuration with JSONB skill fields
- Paginated, user-specific analysis history with full record lookup
- User account data model with unique email addresses
- Argon2 password hashing and verification foundation
- Registration, login, logout, and current-user API endpoints
- Signed sessions stored in HTTP-only, same-site cookies
- Owner-scoped analysis creation, history, and detail access
- Automated quality checks with GitHub Actions and PostgreSQL
- Unit and API tests with pytest
- Browser-level user journey tests with Playwright

## Supported skills

The first version uses a deliberately small vocabulary so the matching behavior stays predictable and easy to test:

- Docker
- FastAPI
- Git
- Java
- JavaScript
- Linux
- PostgreSQL
- Python
- React
- SQL

## Technology

- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, pwdlib, PyJWT, Uvicorn
- **Database:** PostgreSQL, Alembic migrations, SQLite for local fallback and tests
- **Frontend:** HTML, CSS, vanilla JavaScript
- **Testing:** pytest, FastAPI TestClient, Playwright

## Project structure

```text
CareerLens/
├── .github/workflows/ci.yml
├── alembic.ini
├── .env.example
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   └── routes/
│   │   │       ├── analysis.py
│   │   │       ├── auth.py
│   │   │       └── history.py
│   │   ├── core/config.py
│   │   ├── db/
│   │   ├── models/
│   │   │   ├── analysis.py
│   │   │   └── user.py
│   │   ├── schemas/
│   │   │   ├── analysis.py
│   │   │   ├── auth.py
│   │   │   └── history.py
│   │   ├── services/analysis_store.py
│   │   ├── services/passwords.py
│   │   ├── services/sessions.py
│   │   ├── services/skill_extractor.py
│   │   ├── services/scorer.py
│   │   ├── services/user_store.py
│   │   └── main.py
│   ├── migrations/
│   ├── tests/
│   ├── requirements.txt
│   └── requirements-dev.txt
├── e2e/
│   ├── conftest.py
│   └── test_user_journey.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── README.md
```

## Run locally

From the repository root:

```text
python -m venv .venv
```

Activate the environment with PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or with Git Bash:

```bash
source .venv/Scripts/activate
```

Then install the dependencies and start the server:

```text
python -m pip install -r backend/requirements.txt
python -m alembic upgrade head
python -m uvicorn backend.app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Interactive API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Create an account or log in from the main page. The browser sends the HTTP-only session cookie automatically with analysis and history requests.

The health check is available at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

## Database setup

CareerLens uses a local SQLite database by default so the project can be started without additional setup. Database files are ignored by Git.

To use PostgreSQL, create a database and user, copy `.env.example` to `.env`, and replace the example password in `DATABASE_URL`. Then apply the schema:

```text
python -m alembic upgrade head
```

Alembic keeps schema changes versioned and supports both upgrades and downgrades. PostgreSQL stores each skill collection as `JSONB` and uses an ownership-and-date index for user history queries. SQLite foreign-key enforcement is enabled so local ownership constraints match PostgreSQL. Analyses created before accounts were introduced are preserved with no owner, but they are not exposed through authenticated history endpoints.

The development environment includes a local-only authentication secret so the app runs without extra setup. Set `AUTH_SECRET_KEY` to a random value of at least 32 characters before using a production environment. The application refuses to start in production with the development secret.

## API

`POST /api/analyze` requires an authenticated session.

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

`GET /api/analyses?page=1&page_size=10` returns the signed-in user's saved analyses in newest-first order. Page size is limited to 50 records.

`GET /api/analyses/{analysis_id}` returns the complete saved analysis only when it belongs to the signed-in user. Missing and foreign-owned IDs both return `404`.

Authentication endpoints:

- `POST /api/auth/register` creates an account and starts a session.
- `POST /api/auth/login` verifies the email and password and starts a session.
- `POST /api/auth/logout` clears the browser session.
- `GET /api/auth/me` returns the signed-in user or a `401` response.

Registration and login accept JSON containing `email` and `password`. Session tokens are signed, expire after one hour by default, and are stored in an HTTP-only cookie rather than returned in the response body. Cookies are also marked `Secure` when `ENVIRONMENT=production`.

## Tests

Install the development dependencies and Chromium once:

```text
python -m pip install -r backend/requirements-dev.txt
python -m playwright install chromium
```

Run the unit and API tests:

```text
python -m pytest backend/tests
```

Run the browser tests:

```text
python -m pytest e2e --browser chromium
```

The unit and API suite has 101 passing tests covering skill extraction, aliases, edge cases, match scoring, request validation, API responses, persistence, migrations, authentication, authorization, cross-user isolation, session security, user storage, password hashing, history pagination, and frontend serving. One PostgreSQL-specific integration test is skipped locally and runs in CI against a temporary database service.

The two browser tests start the real application with a fresh temporary database. They cover registration, login, invalid credentials, analysis creation, private history, session restoration, logout, and expired-session recovery without changing local development data.

## Continuous integration

GitHub Actions runs the following checks for every pull request and every push to `main`:

- Dependency installation and validation
- Alembic migration upgrade and consistency check
- Complete pytest suite
- PostgreSQL integration test
- Chromium end-to-end tests with failure traces
- Python compilation
- Frontend JavaScript syntax

The workflow uses temporary test credentials and a temporary PostgreSQL service. It does not connect to a development or production database.

## Current limitations

- Skill extraction is rule-based and only recognizes the supported vocabulary above.
- The match score measures skill coverage; it does not consider experience level, years of experience, education, or skill importance.
- History does not yet support searching, filtering, or deleting records.
- The project does not currently use file uploads or OCR.

## Planned next milestone

Prepare the application for production deployment with container configuration, environment-specific settings, health checks, and a managed PostgreSQL database. File uploads, OCR, and React remain deferred until they have a clear role in the project.
