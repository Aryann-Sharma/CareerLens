# Contextual skill extraction

CareerLens fine-tunes `distilbert/distilbert-base-uncased` to predict skill and
knowledge spans. Both BIO prediction heads share the encoder. MiniLM remains a
separate pretrained sentence matcher. The app runs the extractor locally through
ONNX Runtime on CPU, without PyTorch or hosted inference.

## Data and training

Training uses the pinned SkillSpan data and deduplication policy described in the
[CRF baseline guide](training.md): 3,943 training sentences, 2,438 development
sentences, and 2,404 test sentences. Public expert annotations supply the labels;
the app's hand-authored matching fixtures are not training data.

The base model revision is `12040accade4e8a0f71eabdb258fecc2e7e948be`. Its
[model card](https://huggingface.co/distilbert/distilbert-base-uncased) describes
pretraining. The [Apache 2.0 license](third-party/DistilBERT-LICENSE.txt) and
SkillSpan's MIT notice are retained with the artifact.

Five epochs use AdamW, learning rate 0.00003, weight decay 0.01, batch size 16,
seed 42, gradient clipping at 1.0, and linear warmup over 124 batches followed by
linear decay. Mixed precision is enabled on CUDA. The measured run used an RTX
4060 Laptop GPU with 8 GB of memory. Training plus validation took about 153
seconds; downloads, initialization, export, and final evaluation add more time.
CPU-only training is supported but slower.

WordPiece inputs use 256-token windows with 32-token overlap. Only the first
subword of each original word is labelled, and each word is supervised once
across overlapping windows. Tokens removed entirely by BERT normalization use
an unknown token to preserve annotation alignment.

Combined development exact-span F1 selects the checkpoint. Epoch 5 was selected
at 49.93%. The weights and manifest were frozen before test scoring. The ONNX
export check had a maximum absolute logit difference of 0.00000930 against
PyTorch on the verification sample. Seeds and deterministic settings improve
repeatability; hardware and library differences can still change training results.

## Measured results

| SkillSpan test result | Precision | Recall | Exact-span F1 |
| --- | ---: | ---: | ---: |
| Training dictionary, combined | 11.72% | 23.69% | 15.68% |
| CRF baseline, combined | 47.24% | 29.83% | 36.57% |
| DistilBERT, skills | 40.49% | 42.94% | 41.68% |
| DistilBERT, knowledge | 51.86% | 60.16% | 55.71% |
| DistilBERT, combined | 46.30% | 51.35% | 48.70% |

Combined scores pool both heads' true positives, false positives, and false
negatives. Correct predictions need the category and both boundaries. The
improvement over the CRF is 12.13 percentage points, mostly through recall;
precision is slightly lower. This is not token accuracy, fit-score accuracy, or
a state-of-the-art claim.

[contextual-results.json](../evaluation/contextual-results.json) records all
epochs, per-source metrics, error offsets, versions, and data/model checksums.
The roughly 266 MB ONNX model stays outside Git. The measured test inference took
about 74 seconds for 2,404 sentences using four CPU threads; the app uses two
threads and smaller batches, so this is not a per-request latency estimate.

## Independent external check

The [Green corpus](https://github.com/acp19tag/skill-extraction-dataset), by
Thomas A. F. Green, Diana Maynard, and Chenghua Lin, supplies a separate public
human-labelled test set. The selected revision is
`ca1eadd2885a277853b01f0ec96fc89094adf71e`, under
[CC BY 4.0](third-party/Green-LICENSE.txt). It was used only for evaluation after
the model was frozen; no settings were selected on it.

All 336 sentences remain after normalized exact-duplicate checks against all
SkillSpan splits and within Green. This does not prove posting-level independence
or rule out paraphrases. Green has one Skill category, compared here with the
union of SkillSpan skill and knowledge predictions. Other Green categories count
as outside. Different annotation policies make these scores incomparable with
the SkillSpan table.

| Green test result | Precision | Recall | Exact-span F1 |
| --- | ---: | ---: | ---: |
| CRF baseline | 35.91% | 11.69% | 17.63% |
| DistilBERT | 36.41% | 33.88% | 35.10% |

[external-results.json](../evaluation/external-results.json) records provenance,
checksums, counts, and error offsets. These are existing public human annotations,
not newly collected résumé labels. Both evaluations use supplied tokens rather
than PDF text and do not establish résumé extraction accuracy.

## Reproduce the experiment

Use a separate environment for training. These PowerShell commands use the tested
CUDA 12.6 wheel; for CPU-only training, install the same Torch version from the
official CPU wheel index instead.

```powershell
python -m backend.ml.data
python -m venv .venv-training
.venv-training/Scripts/python -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu126
.venv-training/Scripts/python -m pip install -r backend/requirements-training.txt
$env:HF_HOME = Join-Path (Get-Location) '.models/hf-cache'
$env:HF_HUB_DISABLE_XET = '1'
.venv-training/Scripts/python -m backend.ml.train_contextual
```

Initial downloads require internet access. The trainer refuses to overwrite a
completed artifact; choose new `--output` and `--report` paths for another run.
The [Transformers guide](https://huggingface.co/docs/transformers/tasks/token_classification)
explains the subword token-classification task.

After training the CRF baseline and contextual model, use the app environment:

```text
python -m backend.ml.evaluate_external --download
python -m backend.ml.audit_development
python -m alembic upgrade head
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

External data stays in the ignored `.data/green` directory. The
[validation audit](../evaluation/development-errors.json) finds 348 skill misses
with overlapping predictions and 218 without overlap. Knowledge phrases of four
or more words have only 18.18% exact recall, versus 69.35% for single words.
These observations point toward boundary handling and longer phrases as useful
next work; they are not manually adjudicated error causes or test-set tuning.

## Application behavior and limits

`EXTRACTION_MODEL_PATH` defaults to `.models/skillspan-distilbert`. The runtime
verifies hashes and loads only local files. Fixed inputs and weights give
repeatable predictions: learned models can have deterministic inference.

The app combines catalog technologies with additional predicted phrases. Users
can inspect highlighted source text and edit one skill per line. Corrections
replace the scored list and are labelled as reviewed; they do not automatically
retrain the model. The server recalculates scores. Guests must sign in to save;
signed-in analyses and corrected versions create separate history records.

Raw text is split at sentence endings/newlines and at 256 words. WordPiece
overflow windows cover each chunk, but spans crossing chunk boundaries can be
missed. Requests accept up to 50,000 characters. Suggestions exclude phrases
over 100 characters and keep at most 200 skills; source spans remain reviewable.

There is no calibrated confidence score, complete negation handling, or
proficiency assessment. Overlapping phrases can count as separate requirements
until reviewed. MiniLM suggestions cover only catalog skills; other phrases
require exact profile matches. Further work needs independently labelled résumé
data and validated open-vocabulary matching, without repeatedly tuning on these
test sets.

## Filtering suggestions in the app

A model can predict a phrase that is not useful as a skill. For example, in
“be a team worker, and be diligent”, it predicted the article “a” separately.
The application now rejects spans containing only common grammar words,
punctuation, or numbers before building the skill list and calculating the
score. Job analysis, PDF import, and reuse of a saved résumé share this filter.
Rejected spans are also excluded from the highlights shown with those results.
Words inside meaningful phrases are kept, as are short names such as C, R, and IT.

This is a conservative output filter, not another training run. It cannot remove
every incorrect prediction, so users should still review the suggested skills.
The raw `/api/extract` response and the training/evaluation code retain the model's
original spans; the reported benchmark scores have not changed. Existing saved
analyses retain their original results. Run the analysis again to use the filter.

## Technical-skill spelling

The application also has a small explicit map of common technical-skill typos
in `backend/app/services/skill_spelling.py`. It normalizes those spellings for
scoring and records the original token and correction alongside the result.
Other tokens of 5–24 letters can produce review suggestions when they differ
from a catalog alias by one insertion, deletion, substitution, or adjacent
transposition. Several aliases for the same skill yield one candidate. Exact
known names are excluded from guessing. Suggestions are limited to 200 distinct
spellings per document; they do not silently become score requirements.

Users must confirm general suggestions through the skill review controls.
A nearby spelling may be an ordinary word or a different tool, so edit distance
alone is not enough for automatic correction. Free-form soft skills and arbitrary
spelling mistakes are not corrected. The original text and model spans remain
unchanged, and raw extraction and benchmark evaluation still use the original
predictions. These application rules do not retrain either model.
