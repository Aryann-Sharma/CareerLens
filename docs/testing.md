# Testing guide

Run commands from the repository root with the virtual environment activated.

## Verification record

| Date | Check | Result |
| --- | --- | --- |
| 2026-10-13 | Complete backend and Chromium suites after duty-scope fixes, with local extraction/matching models, all context stress sets and the new exported classifier enabled | 1,995 passed; one PostgreSQL-only test skipped |
| 2026-10-13 | Final follow-up corpus/calibration checks and all three new model exports | 8 passed; 186 API variants already covered in the full run; counts overlap |
| 2026-10-13 | Complete backend and Chromium suites after the source-data follow-up, with existing local models and both context stress sets enabled | 1,696 passed; PostgreSQL and the separately checked source-head artifact test skipped |
| 2026-10-13 | Final source-data audits, both exported heads, 80 additional source variants and four conversational-heading imports | 92 passed; overlaps some checks above; compressed JPEG uses an explicit preview correction |
| 2026-10-13 | Complete backend and Chromium suites with all existing local models and the new context workflow stress flag enabled | 1,132 passed; one PostgreSQL-only test skipped |
| 2026-10-13 | Additional exported context-head prediction and expanded split-audit checks | 3 passed; both training variants reproduced the recorded predictions |
| 2026-10-13 | Complete backend and Chromium suites after compound spelling and wider context review; all local model and occupation experiment checks enabled | 744 passed; one PostgreSQL-only test skipped |
| 2026-10-13 | Separate PostgreSQL 18 integration, context-review, and saved-roadmap browser checks | 17 passed |
| 2026-10-13 | Complete backend and Chromium suites after private saved roadmaps; MiniLM, CRF, contextual, and occupation experiment checks enabled | 713 passed; one PostgreSQL-only test skipped |
| 2026-10-13 | Separate PostgreSQL 18 integration plus saved-roadmap and learning browser suites | 22 passed; migration 0007 and schema consistency check passed |
| 2026-10-13 | Complete backend and Chromium suites after learning roadmaps and editor placement changes; MiniLM, CRF, contextual, and occupation experiment checks enabled | 678 passed; one PostgreSQL-only test skipped |
| 2026-10-13 | Separate PostgreSQL 18 integration plus learning-roadmap and spelling-review browser suites | 25 passed; migrations and schema consistency check passed |
| 2026-10-13 | Complete backend and Chromium suites, with MiniLM, CRF, and contextual checks enabled, including workplace spelling review, requirement clauses, seeded inputs, and varied document imports | 612 passed; one PostgreSQL-only test skipped |
| 2026-10-13 | Separate PostgreSQL 18 integration, saved-résumé, job-PDF, varied-document, and requirement-sentence browser checks, before the workplace-spelling follow-up | 33 passed; migrations and migration consistency check passed |
| 2026-10-08 | Separate PostgreSQL integration test and Chromium suite against a disposable PostgreSQL 18 database | 54 passed; migration consistency check passed |
| 2026-10-13 | Installed application dependencies, frontend JavaScript syntax, documentation links, and whitespace | Passed |

The latest photo-upload checks use generated text fixtures, including compressed
JPEG and WebP files; they do not measure accuracy on arbitrary photos. The OCR
models are supplied by the pinned dependency and do not need a test download.

The PDF/photo toolbar and document review were also visually reviewed at 320,
768, and 1,440 pixels. Both attachment buttons fit side by side at 320 pixels.
A delayed session response check confirmed that the upload button stays in place
when the guest account controls appear at all three widths.

The PostgreSQL runs repeat browser coverage against a different database; these
counts should not be added together as unique tests. Extraction and semantic
weights were reused. A separate occupation classifier was trained and evaluated
offline; it is not used in the app (see [experiment](role-experiment.md)). The latest suite reported one upstream
Starlette/AnyIO deprecation warning and no test failures. The context review also
has 32 development cases and 22 additional project-authored evaluation cases;
these are regression fixtures, not an independent accuracy benchmark. See the
[context review notes](context-review.md) for the results and remaining misses.

The [source-backed context experiment](context-source-training.md) contains
748 base examples and 4,965 related training/development/test inputs. A further
12 source paraphrases produce 80 additional evaluation inputs. Model-quality
reports are separate from API stress checks: a valid response and correct
evidence offsets do not establish that a suggested skill is right. Both new
trained heads failed their replacement gates and remain outside app inference.
The conversational-heading JPEG fixture also needs a visible preview correction
because compressed text loses spaces; PDF, PNG and WebP versions import directly.

The [duty-classifier follow-up](context-duty-training.md) adds seven employer
postings and authored duty/background contrasts, taking the combined corpus to
816 base descriptions and 5,417 related inputs. The full suite includes another
186 held-out variants through the preview API. `RUN_FOLLOWUP_HEAD_TESTS=1`
checks both new ridge exports; `RUN_DUTY_HEAD_TESTS=1` verifies the fine-tuned
classifier on all clean test descriptions and checks batch-independent ONNX
inference. The model-quality report separately compares 1,239 unique regression
inputs. Improved aggregate scores do not remove the failed replacement gates.

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
node --check frontend/learning.js
node --check frontend/roadmaps.js
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
| Spelling | Every supported name and alias in multiple casings, multiword aliases, known technical typos, 32 workplace terms with review-only suggestions, uncertain suggestions even when extraction is empty, accept/dismiss keyboard controls, exact-name protection, short names and compounds, original offsets/text/PDF preservation, phrase corrections without duplicate requirements, scores and history, résumé reuse, review overrides, real contextual inference, mobile layout |
| Scoring | Partial and full matches, empty profiles, unknown skills, rounding, preserved ordering |
| Semantic matching | Real local inference, repeatability, explicit denials, ambiguity, similarity thresholds, exact baseline, saved explanations, unavailable-model recovery |
| Trained extraction | Split deduplication, label validation, span metrics, miniature CRF training, artifact integrity, offline prediction, Unicode offsets, contextual word alignment and long inputs, public preview, failure recovery |
| Skill review | Screenshot regression for standalone “a”, grammar-only/punctuation/numeric fragment filtering, preservation of short skills and meaningful phrases, shared PDF/reuse filtering, trained phrases affect scoring, corrected lists override predictions, input limits, source highlighting, original input snapshots, saved extraction evidence |
| Learning plans | All 18 guides, alias and case handling, prerequisite ordering, 80 seeded mixed-skill plans, unknown phrases, reviewed typo choices, six directions, unchanged fit scores, downloadable checked milestones, snapshot preservation, empty plans, errors/retries, logout clearing, late responses, literal text rendering, keyboard dialogs, 320/768/1440-pixel layouts |
| Context review | Source-aligned evidence, opt-in API flag, no score changes until review, saved interpretations, missing-model fallback, 32 development and 22 additional examples with all misses recorded, compound joins and misspellings, casing and hyphens, explicit denials and unrelated sections, real PDF/PNG imports, literal text rendering, analyzed snapshots, phone/desktop review controls |
| Editor placement | Edit shortcut beside the result heading, editor before matched skills, accepted spelling correction focuses the text box with Update analysis in view on phone and desktop |
| Saved roadmaps | Named plans, checked progress, reload/reopen/rename/delete, multiple independent plans, guest sign-in preserving drafts, account isolation, changed-session guards, late success and expired-session responses, lost-response retries without duplicate records, stale update/delete conflicts, saved step snapshots, changed-guide revision checks, pagination and last-page deletion, literal titles, 320/1440-pixel layouts, migration and readiness checks |
| Occupation experiment | Source checksums, conflicting-label removal, split isolation, feature case/typo behavior, acceptance gates, artifact validation, reproduced held-out metrics from actual trained weights; experiment excluded from app recommendations |
| Short skill phrases | Both screenshot regressions, skill-list heading variants, bullets and numbered items, complete team-worker/team-player phrases, generic communication/problem-solving items, original offsets, bounded context batches, prevention of merged requirements or invented source text, exact/semantic scoring, saved history and résumé reuse, unchanged raw extraction and manual overrides |
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

## Varied-input checks

`test_varied_inputs.py` uses seed `20261012` to generate 32 repeatable descriptions
with different technical-skill combinations, casing, list/prose formats, and line
endings. Each runs through catalog and trained extraction, checks expected named
skills, source offsets, deduplication, score arithmetic, and matched/missing lists.
Separate real-model regressions cover requirement sentences, soft skills, irrelevant
text, numbered items with and without spaces, and the reported screenshot examples.

Four documents cover soft-skill prose, full postings with unrelated sections,
technical typos/casing, and numbered skill lists. Each is uploaded as a PDF, PNG,
compressed JPEG, and WebP: 16 document cases. PDFs use separate positioned text
lines. Image tests run the actual local reader. Thirteen cases feed the imported
text directly into trained analysis. Three compressed-image cases explicitly
correct the preview first: JPEG full postings and numbered lists, and a WebP full
posting. They lose shorter spaces or a heading in recognition. These are successful
review workflows, not examples of flawless automatic extraction.

Eight Chromium cases repeat the soft-skill and full-posting documents across all
four formats, including warning visibility, switching between full and selected
text, manual correction where needed, profile matching, and editable skill review.
The screenshot sentence must produce all four phrases and a 25% score when the
profile contains exactly one of them. The high-contrast OCR retry must preserve
every non-whitespace character and fall back when a second reading disagrees.

This collection is a regression suite, not a representative accuracy benchmark.
Exploratory checks still found negation and compound-phrase grouping errors; see
the [model limitations](contextual-model.md#short-phrases-and-skill-lists). Real
handwriting, poor lighting, complex layouts, and arbitrary résumé formats need
broader independent evaluation.

## Trained extraction checks

The [context-head experiment](context-training.md) adds a corpus audit, a
reproducible training control, and 365 real-model preview variants plus 12
document-import flows. Set `RUN_CONTEXT_STRESS_TESTS=1` alongside the other
model flags to run those workflow checks. Generated variants are related
examples, not independent samples; interpretation quality is reported separately
from passing software tests.

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

The integration test checks the real PostgreSQL driver, JSONB fields, indexes, ownership, UTC dates, the account-to-analysis flow, PDF storage and reuse, invalid replacements, and résumé deletion when its owner is removed. It also checks roadmap creation, retry keys, progress updates, version conflicts, private access, and roadmap deletion when its owner is removed. Most other backend tests still use isolated SQLite fixtures. Setting `E2E_DATABASE_URL` runs the complete browser suite against PostgreSQL. Browser test accounts remain in that disposable database after the run.

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
