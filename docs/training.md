# Training the skill extractor

This guide records the CRF baseline. The app now defaults to the
[contextual extractor](contextual-model.md), which uses the same SkillSpan split
policy and has separate held-out and external evaluation reports.

CareerLens includes a supervised extraction experiment trained on the public
SkillSpan dataset. Two linear-chain conditional random fields (CRFs) learn which
words form skill and knowledge phrases in job descriptions. Their parameters are
trained from scratch using labelled examples and L-BFGS optimization on CPU.
MiniLM, used for semantic profile matching, remains a separate pretrained model.

## Data and provenance

The data comes from [SkillSpan](https://github.com/kris927b/SkillSpan), by Mike
Zhang, Kristian Nørgaard Jensen, Sif Dam Sonniks, and Barbara Plank. The authors
describe expert annotation of English job postings in their
[2022 paper](https://aclanthology.org/2022.naacl-main.366/). This experiment uses
the public `house` and `tech` subsets, with the original skill and knowledge BIO
labels. The 72 hand-authored matching fixtures are not used for training.

The downloader pins repository revision
`2ccf3de5b5af7a5409b8dd814fb1315dd6e0ae1b`, records SHA-256 checksums, validates
token/label alignment, and saves the upstream MIT license. A copy of that license
is included in [third-party/SkillSpan-LICENSE.txt](third-party/SkillSpan-LICENSE.txt).
Raw data stays under `.data/skillspan`, outside version control and Docker builds.

Official train, development, and test boundaries are retained. Duplicate
sentences are identified by case-folded tokens with normalized whitespace. The
first occurrence is kept in train, then development, then test; later duplicates
are removed rather than reassigned. This also removes within-split duplicates.

| Split | Original sentences | Retained | Removed |
| --- | ---: | ---: | ---: |
| Training | 4,800 | 3,943 | 857 |
| Development | 3,174 | 2,438 | 736 |
| Test | 3,569 | 2,404 | 1,165 |

Posting IDs restart in each official split. They cannot establish cross-split
posting independence. The audit catches exact sentence duplicates, not all
related postings or paraphrases. These filtered results are not directly
comparable with scores reported on the original dataset.

## Reproduce the experiment

From the repository root, with the project's Python 3.12 environment activated:

```text
python -m pip install -r backend/requirements-ml.txt
python -m backend.ml.data
python -m backend.ml.train
```

Downloading the data needs internet access. Training and prediction run locally
without hosted inference or API charges. The measured run spent about 64 seconds
fitting six candidates on this development machine; total elapsed time also
includes feature extraction, validation, and evaluation and will vary by hardware.

The trainer writes weights and a manifest to `.models/skillspan-crf`, plus a
readable report at `evaluation/training-results.json`. It refuses to overwrite a
completed model. To repeat the experiment, choose separate paths:

```text
python -m backend.ml.train --output .models/skillspan-repeat --report .models/skillspan-repeat/results.json
```

Model files are ignored by Git. The **Train extraction model** workflow repeats
training on relevant pull requests or a manual run and uploads the selected
weights, license, manifest, and report as a temporary workflow artifact.

## What is learned

Each tagger predicts `B` (beginning), `I` (inside), or `O` (outside) for each token.
The skill and knowledge taggers are independent, so their spans may overlap.
The CRF learns both feature weights and label-transition weights.

Features include the word, capitalization, character shape, short prefixes and
suffixes, sentence boundaries, and up to two words on either side. They contain
no gold labels or predefined skill dictionary. A word without a catalog entry
can therefore be included in a predicted span.

Three configurations are declared before evaluation: no neighbouring-word
features with `c1=0.1, c2=0.1`, a two-word window with the same regularization,
and a two-word window with `c2=1.0`. Each uses at most 100 L-BFGS iterations.
The [CRFsuite API](https://python-crfsuite.readthedocs.io/en/latest/pycrfsuite.html)
documents the optimizer and model format.

Development exact-span F1 selects a configuration independently for each tagger.
Both selected a two-word window with `c1=0.1, c2=0.1`. Their manifests are saved
before test predictions are scored. No test results select parameters. L-BFGS
uses a fixed data order here; there is no random train/test split or stochastic
minibatch training. Reproduction across operating systems can have small numerical
differences.

## Measured results

The dictionary baseline collects phrases appearing at least twice in training
annotations and applies longest-first exact matching. It uses the same training
split and test sentences as the CRF. It is a simple baseline for span extraction,
not the app's 18-skill matching system or a state-of-the-art reference.

| Test result | Precision | Recall | Exact-span F1 |
| --- | ---: | ---: | ---: |
| Dictionary: skills | 12.59% | 8.36% | 10.05% |
| Trained CRF: skills | 36.89% | 18.92% | 25.02% |
| Dictionary: knowledge | 11.55% | 39.74% | 17.89% |
| Trained CRF: knowledge | 54.59% | 41.25% | 46.99% |
| Dictionary: combined | 11.72% | 23.69% | 15.68% |
| Trained CRF: combined | 47.24% | 29.83% | 36.57% |

Combined scores pool true positives, false positives, and false negatives across
both taggers. A match requires the correct category and both span boundaries;
partial overlap earns no credit. Correct `O` tokens do not inflate this metric.
An orphan `I` begins a span consistently for predictions and annotations.

The combined improvement is 20.88 F1 percentage points over this dictionary
baseline. It is not an accuracy percentage or evidence that fit scoring improved.
The report includes per-source scores, counts, configuration comparisons, model
checksums, and the first ten errors per category as sentence IDs and token offsets.
Those offsets refer to retained test rows and allow inspection against local data
without republishing job descriptions.

Longer skill phrases remain difficult: their test recall is only 18.92%.
Knowledge phrases perform better, but both false positives and missed spans remain
common. This is an initial classical supervised-learning baseline, not transformer
fine-tuning or a production-quality general skill extractor.

## Try the trained model

```text
python -m backend.ml.predict "Experience with Python and SQL. Excellent communication skills."
```

In the app, paste a job description and expand **Inspect extraction only**
below the analysis panels. The preview lists activity phrases and
knowledge phrases. It does not affect the fit score or save a history record.
The public `POST /api/extract` endpoint accepts `job_description` and returns
span text, category, half-open character offsets, and a model manifest hash.
Offsets count Unicode code points in the trimmed request text, not JavaScript
UTF-16 code units.

The preview accepts up to 50,000 characters. A simple tokenizer preserves source
offsets and splits at newlines or sentence endings, with a 256-token chunk limit.
It processes every chunk, but spans crossing those boundaries can be missed.
Evaluation uses SkillSpan's supplied tokens; raw-text tokenization introduces an
additional source of error that the reported test score does not measure.

Set `EXTRACTION_MODEL_PATH=.models/skillspan-crf` to run this baseline in the app.
The default is the contextual model. Restart the
server after replacing weights because verified model bytes are cached. Model
files and checksums are validated before use; inference never downloads assets.
An absent or damaged model returns `503` for the preview. Other analysis features
remain available. The two selected weight files total about 2.32 MB.

## Next experiments

The [contextual experiment](contextual-model.md) now compares a fine-tuned encoder
against this baseline and adds an external test set. Further work should examine
development boundary errors and independently labelled résumé examples. Keep
these test results fixed rather than repeatedly tuning against them.
