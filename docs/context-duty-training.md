# Duty classifier follow-up

For the later 16-epoch run with 1,632 additional authored descriptions, see the
[context curriculum and promotion check](context-curriculum.md). This document
retains the earlier experiment so its results remain reproducible.

The app now retains short coordinated duties such as “write code, test changes,
deploy releases” when splitting at commas would otherwise discard every part.
It also recognises affirmative modifiers such as “without supervision” and
excludes explicit employee-review commentary and benefits statements from
context suggestions. Ordinary humorous wording is still eligible for review.
These changes preserve original evidence offsets and the six-suggestion limit.

The new classifier described below is **not installed in the application**.
It improves overall coverage considerably, but fails the replacement checks.
Removing its candidate status would overstate the evidence.

## Data and source separation

[The follow-up corpus](../evaluation/context-followup-cases.json) adds 68 base
descriptions: 28 short paraphrases from seven employer postings and 40 authored
contrasts. Each contrast pairs a duty with similar wording used in commentary,
a benefit or a joke. Authored satire is labelled separately from source material.

Sources were retrieved on 13 October 2026:

| Posting | Platform | Split |
| --- | --- | --- |
| [Computer Futures DevOps engineer](https://jobs.smartrecruiters.com/ComputerFutures3/96053576-devops-engineer) | SmartRecruiters | Training |
| [PLS clerical support](https://job-boards.greenhouse.io/plscareers/jobs/5262874008) | Greenhouse | Training |
| [Ownwell property tax consultant](https://job-boards.greenhouse.io/ownwell/jobs/4410174006) | Greenhouse | Development |
| [ClimateWorks program manager](https://apply.workable.com/climateworks-foundation-1/j/AF8F6925B4/) | Workable | Development |
| [Faeth full-stack engineer](https://job-boards.greenhouse.io/faeththerapeutics/jobs/4226314009) | Greenhouse | Test |
| [Squircle Java/UI developer](https://jobs.smartrecruiters.com/SQUIRCLEITCONSULTINGSERVICESPVTLTD/112046595-java-ui-gurgaon) | SmartRecruiters | Test |
| [Knight Arthur sales and marketing](https://jobs.smartrecruiters.com/KnightArthurPromotions1/95405943-must-have-a-sense-of-humor-entry-level-sales-marketing) | SmartRecruiters | Test |

These are readable postings, not a claim that every vacancy remains open.
Each source contributes fewer than 110 paraphrased words. Unavailable pages
and redirects are recorded as exclusions. No applicant or contact information
is included. Skill labels are project judgements, not employer annotations or
independent expert labels. The earlier O*NET attribution and weak-label limits
still apply; see [source training](context-source-training.md).

Combined with the earlier corpus, there are 816 base descriptions: 555 training,
150 development and 111 test. Controlled deletion, transposition, duplication,
joined-word, extra-space and casing variants produce 5,417 inputs: 3,684 training,
993 development and 740 test. Variants remain with their source family. They are
correlated perturbations, not thousands of independently labelled postings.

The earlier 54 regression cases, 365 prior test variants and 80 additional-source
variants remain outside training. These have been inspected in previous runs
and must be described as regression benchmarks rather than blind tests.

## What was trained

Three approaches were evaluated:

1. Keep complete sentences during inference for the previous balanced ridge
   head. This addresses a mismatch with its whole-sentence training inputs.
2. Select ridge regularisation, occupational-task weighting and thresholds for
   each capability on development data. Unsupported labels abstain. This
   overfit development examples and performed poorly on the regression sets.
3. Fine-tune the upper two layers of DistilBERT and a 24-output classifier.
   The lower four layers and embeddings stay frozen. This updates 14,194,200
   parameters, using weighted binary cross-entropy and spelling augmentation.

The third approach ran for 12 epochs on a local RTX 4060 Laptop GPU. Development
precision and F0.5 selected epoch 11 and threshold 0.675. Test descriptions did
not choose the epoch or threshold. The exported ONNX model agrees with the
training model within 0.0000144 absolute error on the export check. CPU tests
also check batch independence and reproduce all 111 clean test predictions.
No paid service or external text-generation model is involved.

## Results and release decision

Precision is the share of suggestions allowed by the project labels. Coverage
is the share of expected skills found. These are capability-review metrics,
not end-to-end accuracy for every skill extracted by the app.

| Regression set | Current precision / coverage | New classifier precision / coverage |
| --- | --- | --- |
| Combined test, 740 variants | 71.6% / 37.4% | 87.2% / 66.6% |
| Clean test, 111 descriptions | 70.6% / 40.9% | 87.0% / 69.9% |
| Earlier 365 variants | 72.2% / 56.8% | 85.2% / 72.8% |
| Original 54 regressions | 95.7% / 85.1% | 93.3% / 78.7% |
| Additional source check, 80 variants | 78.0% / 56.1% | 100% / 48.8% |

On the combined test set, the candidate makes suggestions for 15 negative
examples versus 10 for the current approach. New employer and authored-satire
slices are particularly weak. The aggregate improvement does not excuse those
regressions. The original promotion rule remains: at least 90% precision,
no loss relative to baseline precision or coverage, and no increase in negative
errors on every evaluated set. None of these three candidates passes.

The bounded app fixes are independent of the candidate weights. Their unit
tests cover short coordinated duties, ordinary benefits-related work, actual
denials, affirmative modifiers, commentary and evidence offsets. The older
54 context predictions remain unchanged.

Full predictions: [sentence head](../evaluation/context-sentence-results.json),
[calibrated head](../evaluation/context-calibrated-results.json),
[transformer](../evaluation/context-transformer-results.json), and
[training history](../evaluation/context-transformer-training.json).

## Reproduce

Use the normal app environment for ridge training and evaluation:

```text
python -m backend.ml.train_context_review --data evaluation/context-source-cases.json --output .models/context-head-sentences-v1 --report evaluation/context-sentence-results.json --previous-test evaluation/context-training-cases.json --balance-labels --sentence-context
python -m backend.ml.train_context_calibrated
```

For transformer training, install `backend/requirements-training.txt` with the
appropriate PyTorch wheel, as described in [training](training.md). The pinned
DistilBERT snapshot must already be in `.models/hf-cache`, using revision
`12040accade4e8a0f71eabdb258fecc2e7e948be`. The existing extractor-training setup
downloads this snapshot. Its base-model license is required for export.

```text
python -m backend.ml.train_context_transformer
python -m backend.ml.evaluate_context_transformer
```

Run the second command in the app environment, which also has the sentence
encoder used by the baseline. Use a fresh output directory for another training
run. Artifacts record data checksums, encoder revision, selection settings and
weight checksums. They are kept outside Git and never loaded automatically.

Set `RUN_DUTY_HEAD_TESTS=1` to verify the exported classifier and
`RUN_CONTEXT_STRESS_TESTS=1` to exercise the 186 new held-out spelling variants
through the actual preview pipeline. Corpus and calibration checks run without
model downloads. Existing PDF, image, account, saving and browser tests remain
part of the full suite.

The final local backend/Chromium run passed 1,995 tests with one PostgreSQL-only
test skipped. Eight focused corpus and export checks also passed; these overlap
the full run. The context-training workflow retrains both follow-up ridge heads
and verifies their clean predictions. Transformer training was run locally on
the GPU; the workflow does not retrain that larger model.
