# CareerLens

![CI](https://github.com/Aryann-Sharma/CareerLens/actions/workflows/ci.yml/badge.svg)

CareerLens extracts skills from job descriptions and compares them with a user's profile. Anyone can analyze a role, import skills from a résumé PDF, and correct the extracted list. An account is needed only to save analyses and return to private history.

The project connects a browser interface to a Python API and a relational database. The interface uses HTML, CSS, and JavaScript; the backend uses FastAPI and SQLAlchemy.

## Project status

The main workflows are implemented and tested for local use: guest analysis,
résumé import, skill review, accounts, and private history. The project includes
reproducible training code and measured model comparisons. See the
[testing guide](docs/testing.md) for the latest verification record.

Public hosting has not been set up. Model predictions still need review, and
account recovery and request throttling remain future work. The limitations at
the end of this page describe the current scope.

## Features

- Register, log in, and restore a session using an HTTP-only cookie.
- Analyze immediately without an account, then sign in to save a result.
- Paste a job description and enter a comma-separated list of skills.
- Recognize common aliases, ignore case, and remove duplicate skill mentions.
- Compare skill descriptions with a local pretrained sentence-embedding model.
- Switch to exact matching and compare the score with the semantic result.
- Extract skill phrases using a DistilBERT model fine-tuned on labelled job postings.
- Review highlighted source phrases and correct the skill list before recalculating.
- Import a text-based résumé PDF and review suggested profile skills.
- View matched skills, missing skills, and a percentage score.
- Browse paginated history, open saved evidence, and delete individual analyses.
- Keep each user's history separate, including when switching accounts.
- Use the interface on desktop or mobile, with keyboard-accessible dialogs.
- Run locally with SQLite or use PostgreSQL with versioned Alembic migrations.

## How matching works

The browser starts with **trained extraction + technology catalog**. A fine-tuned DistilBERT tagger finds skill and knowledge phrases in context. The catalog also checks 18 technologies: **CSS, Django, Docker, FastAPI, Git, HTML, Java, JavaScript, Kubernetes, Linux, Machine Learning, Natural Language Processing, Node.js, PostgreSQL, Python, React, SQL, and TypeScript**. Aliases include `js`, `html5`, `css3`, `k8s`, `ml`, `nlp`, `postgres`, and `reactjs`. Catalog-only extraction is available without trained weights.

Catalog skills appear in source order, followed by additional predicted phrases. Longer aliases take precedence, so `React.js` counts as React and does not also count as JavaScript. Repeated names count once. Predictions can overlap or describe the same requirement in different words; use **Review skills and source evidence** to remove mistakes or combine duplicates. **Update analysis** recalculates from the displayed result's original inputs and your corrected job-skill list.

```text
score = round(matched skills / extracted skills * 100)
```

Every listed skill has equal weight. If the list is empty, the score is zero.

The browser starts in **semantic matching** mode. Exact skill names and aliases match first. For other short skill descriptions, a pretrained MiniLM sentence encoder compares the phrase with descriptions of all 18 skills. A suggestion needs a cosine similarity of at least 0.70 and a lead of at least 0.08 over the next skill. For example, “writing relational database queries” can match SQL. Suggestions count toward the semantic score and are listed with the original phrase and similarity value. The exact score is shown alongside them for comparison.

**Exact matching** uses names and aliases. Extraction and matching are separate choices: trained extraction can discover phrases outside the catalog, while MiniLM semantic suggestions currently map only to the 18 catalog skills. Other extracted phrases need an exact, case-insensitive profile match. Results, extraction evidence, and matching evidence are saved together; corrected lists are labelled as reviewed.

Both models run locally on the server's CPU once their files are installed. MiniLM uses downloaded pretrained weights; the contextual extractor uses the project's fine-tuned weights. There are no hosted inference calls or API charges. See the [matching guide](docs/model.md) and [extraction guide](docs/contextual-model.md) for setup, evaluation, and limitations.

The score measures coverage of detected skills. It does not measure hiring probability, experience, education, or suitability for a role. The extractor also does not distinguish required, optional, and negated mentions.

## Stack and structure

| Area | Tools |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy |
| Data | PostgreSQL, SQLite, Alembic |
| Authentication | Argon2 password hashing, signed JWT session cookies |
| Frontend | HTML, CSS, vanilla JavaScript |
| Semantic matching | Pretrained MiniLM sentence embeddings, FastEmbed, ONNX Runtime, NumPy |
| Supervised extraction | PyTorch, Transformers, DistilBERT fine-tuning, BIO tagging, SkillSpan, CRFsuite baseline |
| Document parsing | pypdf, isolated PDF text extraction, reviewed skill import |
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
  ml/             # Data preparation, training, evaluation, and offline prediction
  scripts/        # Model download and evaluation commands
  tests/          # Unit, API, migration, and PostgreSQL tests
frontend/         # Browser interface
e2e/             # Browser tests against a running application
docs/            # Deployment and testing guides
evaluation/      # Labelled development examples and measured results
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
python -m backend.scripts.download_model
python -m alembic upgrade head
python -m uvicorn backend.app.main:app --reload
```

Open [the app](http://127.0.0.1:8000). On a fresh checkout, select **Technology catalog only** under **Skill extraction**: the commands above install MiniLM but do not train or install the contextual extractor. Follow the [contextual training guide](docs/contextual-model.md) to enable the default **Trained model + technology catalog** option.

Choose **Save analysis** on a guest result to sign in or create an account. The [interactive API documentation](http://127.0.0.1:8000/docs) is served by the same application.

Without a `.env` file, the app uses `careerlens.db` in the working directory and a development-only signing secret. Run commands from the repository root. Local database files, model weights under `.models/`, and environment files are ignored by Git. Initial downloads need internet access; subsequent inference does not. If weights are missing, requests needing that model return `503`. Select **Technology catalog only** and **Exact matching** to analyze without either model.

### Short walkthrough

1. Choose **Use example**, then **Analyze my fit**. Review matched and missing skills.
2. Open **Review skills and source evidence**. Edit a skill and choose **Update analysis** to see how the score changes.
3. Under **Import skills from a résumé**, upload a text-based PDF. Review the suggestions and choose **Add to my skills**, then analyze again.
4. Choose **Save analysis**, create an account, and open the saved result under **Recent analyses**.
5. Try deleting a saved analysis, then log out. Private results and drafts are cleared.

For a local demonstration, explain the difference between extracting phrases and
matching skills, then show one correct prediction and one correction. The
reported F1 scores measure span extraction, not hiring probability.

### PostgreSQL and containers

To use an existing PostgreSQL database, copy `.env.example` to `.env`, set `DATABASE_URL` and `AUTH_SECRET_KEY`, then run `python -m alembic upgrade head`. The URL must use the installed driver: `postgresql+psycopg://user:password@host:5432/database`. URL-encode reserved characters in database credentials.

For a local application and PostgreSQL stack, follow the [deployment guide](docs/deployment.md). It covers Compose configuration, migrations, health checks, and production settings.

## Train and try the skill extractor

The current extractor fine-tunes DistilBERT on SkillSpan's public, expert-labelled
job postings. It retains the official splits, removes duplicate sentences, and
selects a checkpoint using development data. On 2,404 retained test sentences,
combined exact-span F1 is **48.70%**, compared with **36.57%** for the trained CRF
and **15.68%** for a training-dictionary baseline. These are span-extraction
measurements, not fit-score accuracy. A separate, independently labelled Green
test set gives **35.10%** for DistilBERT and **17.63%** for the CRF under a documented
label mapping. Different annotation policies make the two benchmarks incomparable.

```text
python -m pip install -r backend/requirements-ml.txt
python -m backend.ml.data
python -m backend.ml.train
python -m backend.ml.predict "Experience with Python and SQL. Excellent communication skills."
```

The commands above reproduce the small CRF baseline. Follow the
[contextual training guide](docs/contextual-model.md) to fine-tune DistilBERT in a
separate environment and export its CPU inference model. The app defaults to
`.models/skillspan-distilbert`; set `EXTRACTION_MODEL_PATH=.models/skillspan-crf`
to use the baseline instead. With no extraction weights installed, select
**Technology catalog only**. The [baseline guide](docs/training.md) documents the
CRF experiment and shared data preparation. Inference is repeatable for fixed
inputs and weights; the trained parameters are learned from data.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Create an account and start a session |
| POST | `/api/auth/login` | Start a session |
| POST | `/api/auth/logout` | Clear the browser's session cookie |
| POST | `/api/extract` | Preview trained extraction from up to 50,000 characters; no account needed |
| POST | `/api/resume?method=trained` | Read a raw PDF body and suggest profile skills; no account needed |
| GET | `/api/auth/me` | Return the signed-in user |
| POST | `/api/analyze` | Analyze and save a job description |
| POST | `/api/preview` | Analyze without an account or database writes |
| GET | `/api/analyses` | List the signed-in user's history |
| GET | `/api/analyses/{id}` | Open one owned analysis |
| DELETE | `/api/analyses/{id}` | Delete one owned analysis; returns `204` |
| GET | `/health/live` | Check that the application responds |
| GET | `/health/ready` | Check the database connection and required table columns |

`/health` is an alias for `/health/live`. `/api/preview`, `/api/extract`, and `/api/resume` are public and do not save data. `/api/analyze` and all history routes require authentication. A missing or foreign-owned analysis returns `404`.

Guest results stay in the current page's memory and disappear on refresh or navigation. Choosing **Save analysis** opens sign-in and saves the analyzed input after successful authentication. Editing the form does not change which inputs that result represents. The server recalculates the result when saving; it never accepts client-supplied scores. Cancelling sign-in keeps the result without saving it. Signing in through the header preserves a guest result but requires a separate save click. New analyses completed while signed in continue to save automatically.

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

The API defaults to `"matching_method": "exact"` and `"extraction_method": "catalog"` for compatibility. Set them to `"semantic"` and `"trained"` for model-assisted analysis. Semantic responses add `matching_details`, including the model revision, thresholds, exact baseline, and suggestions. Trained responses add `extraction_details` with source offsets and model provenance. Optional `reviewed_job_skills` replaces the extracted list and records the method as reviewed; it accepts the same count/length limits as profile skills. Saved responses include a `Location` header for the created history record. Detail lookups retain this evidence.

PDF import accepts `Content-Type: application/pdf`, at most 5 MB, 10 pages, and 50,000 extracted characters. Text parsing runs in a separate process with a 12-second timeout and decompression limits. Password-protected and scanned/image-only PDFs are rejected with an explanation; OCR is not included. Use `method=catalog` to import without trained weights. The PDF and full extracted résumé text are not saved. Only skills explicitly added to the profile become part of a subsequently saved analysis.

History uses `page` and `page_size`, with defaults of 1 and 10. Pages range from 1 to 2,147,483,647; page size ranges from 1 to 50. The browser shows five records per page. Results are ordered newest first, with the record ID breaking timestamp ties. API timestamps include a UTC offset; the browser displays them in the user's timezone.

Registration and login accept `email` and `password`. Email addresses are normalized for case-insensitive lookup. Registration requires a password of 12–128 characters. Sessions last 60 minutes by default and use HTTP-only, SameSite=Lax cookies; production also enables Secure cookies. Logout clears the cookie, while previously issued tokens remain valid until expiry. Explicit logout clears the draft and displayed results. After a session expires, the draft is restored only when the same account signs back in.

## Tests and continuous integration

Install the development dependencies and browser:

```text
python -m pip install -r backend/requirements-dev.txt
python -m backend.scripts.download_model
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

- Semantic suggestions cover the 18-skill catalog; other predicted phrases currently need exact profile matches.
- Similarity can mistake related concepts for equivalent skills. It is not evidence of proficiency, and some valid paraphrases are deliberately left unmatched.
- Semantic matching uses small, hand-authored development fixtures. Extraction uses public labelled data with held-out and external span metrics.
- Trained extraction still misses and mislabels phrases. The review controls are important; the score does not assess proficiency or hiring probability.
- Résumé formatting and raw-text tokenization can introduce errors not measured by the tokenized job-posting benchmarks. Scanned PDFs are unsupported.
- History has no search or filtering controls.
- Accounts have no email verification, password reset, or session revocation.
- Request throttling is not built in; a public deployment needs rate limits at the proxy or application layer.
- Hosting and a managed production database are not configured in this repository.

Further model work should focus on phrase boundaries, independently labelled résumé examples, and matching open-ended skill phrases. MiniLM remains pretrained; DistilBERT is fine-tuned and the CRF baseline is trained from scratch. Public deployment has not been performed.
