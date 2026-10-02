# CareerLens

![CI](https://github.com/Aryann-Sharma/CareerLens/actions/workflows/ci.yml/badge.svg)

CareerLens is a full-stack job-description analysis app for students and job seekers. Paste a job description, enter your current skills, and receive a clear breakdown of required, matched, and missing skills with a match score.

The current MVP has a working browser interface connected to a FastAPI backend. It can extract supported skills from a job description, compare them with a user's skills, calculate a match score, save the analysis, and show the result in the browser.

## How it works

1. The user enters a job description and a list of their skills in the browser.
2. The frontend sends the data to `POST /api/analyze` as JSON.
3. Pydantic validates and cleans the request before it reaches the analysis logic.
4. The skill extractor searches the description using a curated list of skills and common aliases.
5. The scorer compares the extracted skills with the user's skills.
6. SQLAlchemy saves the request and result in the database.
7. The API returns the extracted, matched, and missing skills with a percentage score.
8. The frontend displays the result and refreshes the recent-analysis history without reloading the page.

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
- FastAPI request validation and API documentation
- Database persistence through SQLAlchemy
- Versioned database migrations with Alembic
- PostgreSQL configuration with JSONB skill fields
- Paginated analysis-history dashboard with full record lookup
- Automated quality checks with GitHub Actions and PostgreSQL
- Unit and API tests with pytest

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

- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, Uvicorn
- **Database:** PostgreSQL, Alembic migrations, SQLite for local fallback and tests
- **Frontend:** HTML, CSS, vanilla JavaScript
- **Testing:** pytest and FastAPI TestClient

## Project structure

```text
CareerLens/
├── .github/workflows/ci.yml
├── alembic.ini
├── .env.example
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── analysis.py
│   │   │   └── history.py
│   │   ├── core/config.py
│   │   ├── db/
│   │   ├── models/analysis.py
│   │   ├── schemas/
│   │   │   ├── analysis.py
│   │   │   └── history.py
│   │   ├── services/analysis_store.py
│   │   ├── services/skill_extractor.py
│   │   ├── services/scorer.py
│   │   └── main.py
│   ├── migrations/
│   ├── tests/
│   └── requirements.txt
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

The health check is available at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

## Database setup

CareerLens uses a local SQLite database by default so the project can be started without additional setup. Database files are ignored by Git.

To use PostgreSQL, create a database and user, copy `.env.example` to `.env`, and replace the example password in `DATABASE_URL`. Then apply the schema:

```text
python -m alembic upgrade head
```

Alembic keeps schema changes versioned and supports both upgrades and downgrades. PostgreSQL stores each skill collection as `JSONB` and indexes analyses by creation time for the history view.

## API

`POST /api/analyze`

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

`GET /api/analyses?page=1&page_size=10` returns saved analyses in newest-first order. Page size is limited to 50 records.

`GET /api/analyses/{analysis_id}` returns the complete saved analysis or a `404` response when it does not exist.

## Tests

```text
python -m pytest backend/tests
```

The local test suite contains 72 tests covering skill extraction, aliases, edge cases, match scoring, request validation, API responses, persistence, migrations, history pagination, and frontend serving. CI also runs a PostgreSQL-specific integration test against a temporary database service.

## Continuous integration

GitHub Actions runs the following checks for every pull request and every push to `main`:

- Dependency installation and validation
- Alembic migration upgrade and consistency check
- Complete pytest suite
- PostgreSQL integration test
- Python compilation
- Frontend JavaScript syntax

The workflow uses temporary test credentials and a temporary PostgreSQL service. It does not connect to a development or production database.

## Current limitations

- Skill extraction is rule-based and only recognizes the supported vocabulary above.
- The match score measures skill coverage; it does not consider experience level, years of experience, education, or skill importance.
- Analysis history is shared locally because user accounts have not been added yet.
- History does not yet support searching, filtering, or deleting records.
- The project does not currently use authentication, file uploads, or OCR.

## Planned next milestone

Add authentication and user-specific profiles so each person has private analysis history. File uploads, OCR, React, Docker, continuous deployment, and production hosting are intentionally deferred until they have a clear role in the project.
