# CareerLens

CareerLens is a full-stack job-description analysis app for students and job seekers. Paste a job description, enter your current skills, and receive a clear breakdown of required, matched, and missing skills with a match score.

The current MVP has a working browser interface connected to a FastAPI backend. It can extract supported skills from a job description, compare them with a user's skills, calculate a match score, and show the result in the browser.

## How it works

1. The user enters a job description and a list of their skills in the browser.
2. The frontend sends the data to `POST /api/analyze` as JSON.
3. Pydantic validates and cleans the request before it reaches the analysis logic.
4. The skill extractor searches the description using a curated list of skills and common aliases.
5. The scorer compares the extracted skills with the user's skills.
6. The API returns the extracted, matched, and missing skills with a percentage score.
7. The frontend displays the result without reloading the page.

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

- **Backend:** Python, FastAPI, Pydantic, Uvicorn
- **Frontend:** HTML, CSS, vanilla JavaScript
- **Testing:** pytest and FastAPI TestClient

## Project structure

```text
CareerLens/
├── backend/
│   ├── app/
│   │   ├── api/routes/analysis.py
│   │   ├── core/config.py
│   │   ├── schemas/analysis.py
│   │   ├── services/skill_extractor.py
│   │   ├── services/scorer.py
│   │   └── main.py
│   ├── tests/
│   ├── .env.example
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
python -m uvicorn backend.app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Interactive API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

The health check is available at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

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

## Tests

```text
python -m pytest backend/tests
```

The current test suite contains 61 tests covering skill extraction, aliases, edge cases, match scoring, request validation, API responses, and frontend serving.

## Current limitations

- Skill extraction is rule-based and only recognizes the supported vocabulary above.
- The match score measures skill coverage; it does not consider experience level, years of experience, education, or skill importance.
- Analyses are not stored yet, so refreshing the page clears the result.
- The project does not currently use authentication, file uploads, OCR, or an external AI service.

## Planned next milestone

Add PostgreSQL persistence and an analysis-history dashboard. Authentication, file uploads, OCR, external AI services, React, Docker, CI/CD, and deployment are intentionally deferred until the core workflow is stable.
