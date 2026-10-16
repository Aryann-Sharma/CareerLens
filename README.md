# CareerLens

CareerLens is a web app that compares the skills in a resume with a job description and turns the gaps into a learning plan. I built the frontend, API and database, and added local NLP models to extract and match skills.

You can try an analysis without an account. Signing in lets you save your results, resume and learning roadmaps.

## What it does

- Imports text-based resume PDFs and job descriptions from text, PDFs or images.
- Finds skills in context and shows the source text so you can correct the results.
- Compares your skills with the role using exact matching or sentence embeddings.
- Suggests learning steps and lets you save roadmap progress.
- Keeps saved analyses and files separate for each account.

The app runs locally. It has not been publicly deployed.

## How it works

The HTML/CSS/JavaScript frontend calls a FastAPI backend. SQLAlchemy handles storage, with SQLite for a simple local setup or PostgreSQL with Alembic migrations. Accounts use Argon2 password hashing and JWT session cookies.

There are two separate NLP steps:

1. **Extraction:** a DistilBERT model fine-tuned on SkillSpan identifies skill and knowledge phrases. I also trained a CRF baseline to compare against it.
2. **Matching:** a pretrained MiniLM model compares extracted phrases with the app's skill catalog. It uses a similarity threshold and a margin over the next candidate to avoid accepting every related phrase.

The exported extractor runs through ONNX Runtime on CPU. MiniLM is pretrained; I did not fine-tune it. Users can edit the extracted skills before the app recalculates the result.

## Model results

Both models below use the same deduplicated SkillSpan test split of **2,404 sentences** and the same combined exact-span scoring for skills and knowledge.

| Model | Precision | Recall | Exact-span F1 |
| --- | ---: | ---: | ---: |
| CRF baseline | 47.24% | 29.83% | 36.57% |
| Fine-tuned DistilBERT | 46.30% | 51.35% | 48.70% |

DistilBERT improved F1 by **12.13 points**, mainly by finding more of the labelled spans. Precision was slightly lower. An exact match requires both the correct category and phrase boundaries.

On the separate Green test set, DistilBERT reached 35.10% F1 versus 17.63% for the CRF. Green uses a different annotation scheme, so its scores should not be compared directly with SkillSpan.

The [training guide](https://github.com/Aryann-Sharma/CareerLens/blob/main/docs/contextual-model.md) explains the splits, checkpoint selection, ONNX export and limitations. The [DistilBERT report](https://github.com/Aryann-Sharma/CareerLens/blob/main/evaluation/contextual-results.json) and [CRF report](https://github.com/Aryann-Sharma/CareerLens/blob/main/evaluation/training-results.json) contain the recorded results.

## Run locally

Use Python 3.12 and run these commands from the repository root:

```text
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS or Linux
source .venv/bin/activate
```

Then install the app, download the matching model and start the server:

```text
python -m pip install -r backend/requirements.txt
python -m backend.scripts.download_model
python -m alembic upgrade head
python -m uvicorn backend.app.main:app --reload
```

Open [localhost:8000](http://127.0.0.1:8000). On a fresh checkout, select **Find listed technical skills** under **How to find skills**. The setup above downloads MiniLM but does not install the fine-tuned extractor. Follow the [contextual model guide](https://github.com/Aryann-Sharma/CareerLens/blob/main/docs/contextual-model.md) to train and export that model.

Without either model, **Find listed technical skills** and **Match skill names only** let you use the catalog-based workflow. The first model download needs internet access; inference runs locally afterwards.

The default setup uses SQLite and a development signing secret. For PostgreSQL, Docker Compose and production configuration, see the [deployment guide](https://github.com/Aryann-Sharma/CareerLens/blob/main/docs/deployment.md).

## Tests

```text
python -m pip install -r backend/requirements-dev.txt
python -m playwright install chromium
python -m pytest backend/tests -q
python -m pytest e2e --browser chromium -q
```

The GitHub Actions [CI workflow](https://github.com/Aryann-Sharma/CareerLens/blob/main/.github/workflows/ci.yml) checks API behaviour, account isolation, migrations, PostgreSQL integration, browser journeys and the Docker build. The [testing guide](https://github.com/Aryann-Sharma/CareerLens/blob/main/docs/testing.md) covers the extra model and database checks.

## Limits and decisions

- The score measures coverage of detected skills, not hiring probability or proficiency. Extraction can miss phrases or include the wrong ones, which is why the review step is part of the app.
- MiniLM suggestions map to an 18-skill catalog. Other extracted phrases need an exact profile match.
- Resume PDFs need selectable text. Job-image OCR has a review step and does not make scanned resume PDFs readable.
- Accounts do not yet have email verification, password reset or token revocation. Public hosting would also need request throttling and production configuration.
- I kept newer context-classification experiments out of the app when they failed the regression checks, even when their aggregate scores improved. Their reports remain in the repository.

More detail: [semantic matching](https://github.com/Aryann-Sharma/CareerLens/blob/main/docs/model.md), [learning roadmaps](https://github.com/Aryann-Sharma/CareerLens/blob/main/docs/learning.md), [context review](https://github.com/Aryann-Sharma/CareerLens/blob/main/docs/context-review.md).
