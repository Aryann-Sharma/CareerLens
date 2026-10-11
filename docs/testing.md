# Testing guide

Run commands from the repository root with the virtual environment activated.

## Verification record

| Date | Check | Result |
| --- | --- | --- |
| 2026-10-12 | Complete backend and Chromium suites, with MiniLM, CRF, and contextual integration checks enabled, including PDF/photo job imports and section selection | 444 passed; one PostgreSQL-only test skipped |
| 2026-10-12 | Separate PostgreSQL 18 integration test, saved-résumé browser checks, and job-PDF browser checks | 22 passed; fresh migrations and migration consistency check passed |
| 2026-10-08 | Separate PostgreSQL integration test and Chromium suite against a disposable PostgreSQL 18 database | 54 passed; migration consistency check passed |
| 2026-10-12 | Installed application dependencies, frontend JavaScript syntax, documentation links, and whitespace | Passed |

The latest photo-upload checks use clear generated text fixtures; they do not measure accuracy on arbitrary photos. The OCR models are supplied by the pinned dependency and do not need a test download.

The PDF/photo toolbar and document review were also visually reviewed at 320,
768, and 1,440 pixels. Both attachment buttons fit side by side at 320 pixels.
A delayed session response check confirmed that the upload button stays in place
when the guest account controls appear at all three widths.

The PostgreSQL runs repeat browser coverage against a different database; these
counts should not be added together as unique tests. Model weights were reused
for the latest checks, not retrained. The latest suite reported one upstream
Starlette/AnyIO deprecation warning and no test failures.

These checks support the implemented local workflows. They do not establish
production load capacity, browser compatibility beyond Chromium, or accuracy on
every résumé format. Docker runtime and public HTTPS deployment remain unverified
locally. See the [deployment guide](deployment.md) for those separate checks and
the [contextual model guide](contextual-model.md) for measured extraction quality.

## Install test dependencies

```text
python -m pip install -r backend/requirements-dev.txt
python -m backend.scripts.download_model
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

Most semantic tests use controlled model rankings to check thresholds, ambiguity,
ownership, persistence, and failure handling. To test the real model offline and
check repeatability, set `$env:RUN_MODEL_TESTS = '1'` in PowerShell before running
the backend suite. Remove it afterwards with `Remove-Item Env:RUN_MODEL_TESTS`.
Browser tests exercise the real model, so download it before running them.

Run `python -m backend.scripts.evaluate_matching` to regenerate
`evaluation/results.json`. The [model guide](model.md) explains how to read the
development results and why they are not a production accuracy claim.

The browser fixture applies migrations to a temporary SQLite database and starts the real application on an available loopback port. Each test gets a fresh browser context, and the server is stopped after the suite. Tests fail on uncaught browser errors. Playwright writes retained failure traces under `test-results/`.

## Feature coverage

| Feature | Checks |
| --- | --- |
| Extraction | Every supported skill and alias, case, duplicates, punctuation, overlapping names, word boundaries, repeated input |
| Spelling | Every supported name and alias in multiple casings, multiword aliases, known technical typos, uncertain suggestions that require review, exact-name protection, short names and compounds, original offsets/text/PDF preservation, deduplication, scores and history, résumé reuse, review overrides, real contextual inference, mobile layout |
| Scoring | Partial and full matches, empty profiles, unknown skills, rounding, preserved ordering |
| Semantic matching | Real local inference, repeatability, explicit denials, ambiguity, similarity thresholds, exact baseline, saved explanations, unavailable-model recovery |
| Trained extraction | Split deduplication, label validation, span metrics, miniature CRF training, artifact integrity, offline prediction, Unicode offsets, contextual word alignment and long inputs, public preview, failure recovery |
| Skill review | Screenshot regression for standalone “a”, grammar-only/punctuation/numeric fragment filtering, preservation of short skills and meaningful phrases, shared PDF/reuse filtering, trained phrases affect scoring, corrected lists override predictions, input limits, source highlighting, original input snapshots, saved extraction evidence |
| Job image import | Real offline PNG/JPEG/WebP recognition, unsaved guest uploads, byte/pixel/dimension limits, EXIF rotation, transparent backgrounds, animation and blank-image rejection, timeout and busy recovery, camera-button file picker and keyboard access, editable preview, multiple photos appended without overwriting typed text, editing the combined description, text limits, discard during reading and restored focus, logout and upload races, literal text rendering, mobile/tablet/desktop layout |
| Job PDF and section selection | Real PDF and photo extraction from full postings, required/preferred skills retained, clearly labelled unrelated sections omitted, original text available, unclear headings keep full text, unknown headings retained, PDF limits and retry, private review cleared on logout, PDF/photo switching races, mixed-source appends, editable combined text, literal original-text preview, responsive attachment controls |
| Résumé import | PDF validation, byte/page/text limits, encrypted and image-only documents, parser timeout, reviewed profile import, no database writes, ignored upload responses after logout |
| Saved résumé | Authenticated save/download/reuse/delete, account isolation, replacement validation, user deletion cascade, migration consistency, guest sign-in after upload, retries, late responses after logout, mobile layout |
| Guest access | Immediate workspace, exact and semantic preview without database access, private save/history routes, sign-in-to-save, cancellation, retries, preserved result snapshots, delayed session checks |
| Validation | Missing and extra fields, incorrect types, blank descriptions, input limits |
| Accounts | Registration, duplicate email, password validation and hashing, login errors, session restoration, logout |
| Sessions | Invalid and expired tokens, deleted users, production cookie flags |
| Privacy | Ownership checks, foreign IDs, legacy unowned records, cleared drafts, ignored responses after logout |
| History | Persistence, newest-first ordering, pagination, previews, saved evidence, deletion ownership, confirmation/cancellation, retry, last-page recovery |
| Browser recovery | Failed analysis requests and retries, unavailable history, missing details, expired sessions |
| Interface | Example input, score and skill displays, keyboard dismissal, dialog padding, button alignment and touch targets, seven viewport widths from 320 to 1,440 pixels, mobile long content, literal text rendering |
| Database | Migrations, schema consistency, write rollback, uniqueness, foreign keys, PostgreSQL JSONB |
| Operations | Liveness, database readiness, missing schema, production configuration |

## Trained extraction checks

The contextual model has separate offline, Unicode-offset, repeated-inference,
and long-input checks. Its alignment tests cover overlapping windows and control
characters removed by tokenization. Enable `RUN_CONTEXTUAL_TESTS=1` after following
the [contextual training guide](contextual-model.md). `RUN_EXTRACTOR_TESTS=1`
enables the CRF and extraction API checks; `RUN_MODEL_TESTS=1` enables MiniLM.

Backend tests cover trained/reviewed scoring, saved extraction evidence,
deletion ownership and identifier bounds, PDF byte/page/text limits, encrypted
and image-only PDFs, parser timeouts, and unsaved guest imports. Browser tests
exercise source highlights, literal HTML rendering, corrections using the original
analysis snapshot, reviewed PDF skill import, 320/768/1440-pixel layouts, stale
upload responses after logout, and deletion with cancel, retry, and last-page recovery.

```powershell
$env:RUN_CONTEXTUAL_TESTS = '1'
$env:RUN_EXTRACTOR_TESTS = '1'
$env:RUN_MODEL_TESTS = '1'
python -m pytest backend/tests e2e --browser chromium -q
Remove-Item Env:RUN_CONTEXTUAL_TESTS, Env:RUN_EXTRACTOR_TESTS, Env:RUN_MODEL_TESTS
```

The ordinary backend suite trains a small synthetic fixture to verify the full
training pipeline. This fixture is a software test, not the SkillSpan experiment
or a source of reported model quality. Browser tests mock preview responses to
cover layout, input limits, safe text rendering, errors, edits, and logout.

To check the actual trained weights, first follow the [training guide](training.md),
then enable the integration checks in PowerShell:

```powershell
$env:RUN_EXTRACTOR_TESTS = '1'
python -m pytest backend/tests/test_ml_training.py backend/tests/test_trained_extraction.py -q
$env:RUN_CONTEXTUAL_TESTS = '1'
python -m pytest e2e/test_review_upload_delete.py e2e/test_saved_resume.py --browser chromium -q
Remove-Item Env:RUN_CONTEXTUAL_TESTS
Remove-Item Env:RUN_EXTRACTOR_TESTS
```

The real-model check blocks outbound socket connections during inference and
checks repeated predictions and source offsets. The browser check verifies an
actual prediction from the local model. The separate training workflow runs
the training and backend checks; the main CI suite does not retrain on every
application change.

On Windows, if an old system temporary directory is inaccessible, give pytest a
new directory under `.review-tests` using `--basetemp=.review-tests/my-test-run`
and disable pytest's cache with `-p no:cacheprovider` if necessary.
Choose an unused path: pytest clears the specified base directory when starting.

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

The integration test checks the real PostgreSQL driver, JSONB fields, indexes, ownership, UTC dates, the account-to-analysis flow, PDF storage and reuse, invalid replacements, and résumé deletion when its owner is removed. Most other backend tests still use isolated SQLite fixtures. Setting `E2E_DATABASE_URL` runs the complete browser suite against PostgreSQL. Browser test accounts remain in that disposable database after the run.

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
