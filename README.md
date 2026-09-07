# CareerLens

CareerLens is a full-stack job-description analysis app for students and job seekers. Paste a job description, enter your current skills, and receive a clear breakdown of required, matched, and missing skills with a match score.

This repository currently contains milestone 1: a working browser interface connected to a FastAPI backend with rule-based skill extraction, match scoring, validation, and tests.

## Current features

- Rule-based extraction from a curated technical-skill vocabulary
- Alias handling (for example, `js` becomes `JavaScript` and `postgres` becomes `PostgreSQL`)
- Case-insensitive matching with duplicate removal
- Transparent match score based on the percentage of required skills covered
- Responsive HTML/CSS/JavaScript frontend
- FastAPI request validation and API documentation
- Unit and API tests with pytest

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
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Interactive API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

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

```powershell
python -m pytest backend\tests
```

## Planned next milestone

Add PostgreSQL persistence and an analysis-history dashboard. Authentication, file uploads, OCR, LLM APIs, Java services, React, Docker, CI/CD, and deployment are intentionally deferred until the core workflow is stable.
