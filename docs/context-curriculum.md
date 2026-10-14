# Context curriculum and promotion check

The larger context classifier is still a candidate. Its aggregate precision is
better than the current context suggestions, but it does not pass every release
check. The app continues to use its existing extractor and context suggestions.

## Training data

The [curriculum](../evaluation/context-curriculum-cases.json) adds 1,632 authored
base descriptions across the 24 capability categories. Each category has nine
training duties and three development duties. Each duty also appears as an
optional course, a quotation, and training provided by an employer. These
contrasts teach the difference between work assigned to an applicant and similar
words used elsewhere in a posting. Mixed-duty examples use only components from
the same split.

Together with the earlier source and follow-up corpora, there are 2,448 base
descriptions: 1,819 training, 518 development and 111 test. Spelling perturbations
produce 12,053 training inputs, 3,445 development inputs and 740 test inputs.
These variants are correlated, not independent labelled vacancies. The labels
are project judgements and occupational weak labels, not independently verified
expert annotations. No old test description was added to training.

The deterministic [builder](../backend/ml/context_curriculum.py) and split tests
check that core duties, contextual variants and composition components remain
in their assigned split. The earlier source attribution still applies; see
[source training](context-source-training.md).

## Training and passage handling

The run fine-tuned the upper two DistilBERT layers and a 24-output classifier:
14,194,200 trainable parameters. The base revision, package versions, settings,
checksums and per-epoch results are in the
[training report](../evaluation/context-curriculum-training.json).

Training ran for 16 epochs on the local RTX 4060 Laptop GPU, with about 21 minutes
of recorded epoch time. Development precision and F0.5 selected epoch 16 and a
0.95 threshold. Test results did not select the checkpoint or threshold. The
threshold is an operating setting, not a calibrated probability of correctness.

The candidate reads passages instead of isolated sentences, retaining the
context around quotations and employer-provided training. Windows contain up
to 140 words with overlap and a maximum of 48 windows per description. Model
inputs are limited to 256 subword tokens, so unusually dense text can still be
truncated. Original offsets are preserved. The old sentence view remains
available to reproduce earlier experiments.

The ONNX export differed from the training model by at most 0.0000296 on its
export check. Further tests reproduce recorded predictions, compare batched and
individual inference, and check empty inputs. This verifies export behaviour;
it does not establish correctness on every possible job description.

## Fresh check

The [fresh check](../evaluation/context-promotion-check.json) was fixed before
evaluating this candidate. It contains 12 short paraphrases from three readable
employer postings and 20 separately authored edge cases, producing 217 inputs
with spelling and casing variants. Each employer contributes fewer than 100
paraphrased words. Sources were checked on 14 October 2026:

- [Tieto project manager](https://jobs.smartrecruiters.com/tieto2/744000152402730)
- [HiWave social content intern](https://jobs.smartrecruiters.com/HiWave/743999843660109-tiktok-intern)
- [Energy Exemplar support analyst](https://job-boards.greenhouse.io/energyexemplarllc/jobs/5417736008?gh_src=be7d93548us)

Redirected Workable postings and inaccessible pages were excluded and recorded.
This is not a claim that the postings are still accepting applications. Humorous
and metaphorical authored cases are identified as authored, not attributed to
employers. After this evaluation, the check is a regression set for future work.

## Results

Precision is the share of suggested capabilities allowed by the labels. Coverage
is the share of expected capabilities found. These measure the context feature,
not overall application accuracy or the separate skill-span extractor.

| Set | Current precision / coverage | Candidate precision / coverage |
| --- | --- | --- |
| Combined test, 740 inputs | 71.6% / 37.4% | 94.4% / 66.3% |
| Clean test, 111 descriptions | 70.6% / 40.9% | 95.5% / 66.7% |
| Original 54 regressions | 95.7% / 85.1% | 97.6% / 83.0% |
| Earlier 365 variants | 72.2% / 56.8% | 87.4% / 79.1% |
| Additional source check, 80 inputs | 78.0% / 56.1% | 100% / 48.8% |
| Fresh check, 217 inputs | 77.7% / 44.2% | 98.5% / 60.0% |
| Fresh employer subset | 79.4% / 61.6% | 100% / 50.5% |

The candidate produces no false suggestions on negative cases in the combined
or fresh checks. However, it produces one in the original 54 regressions and
eight among the earlier 365 variants. It also loses coverage on the additional
source check and fresh employer subset. Five evaluated sets fail the unchanged
promotion rule: precision at least 90% and no worse than baseline, coverage no
worse than baseline, and no increase in negative-case errors on every set.

All predictions and failures are retained in the
[evaluation report](../evaluation/context-curriculum-results.json). The full
evaluation covers 1,456 unique inputs; overlapping slices are not additional
independent cases. Do not use an aggregate improvement to hide a failed slice.

Before promotion, further work should broaden the contextual contrasts, address
missed employer duties, and use development checks separated by data source so
the authored examples cannot dominate model selection. New independent labels
would strengthen the evidence. More epochs alone did not solve these problems.

## Reproduce

Use the environments and pinned base-model cache described in
[duty training](context-duty-training.md). Choose a new output directory for
each run; training refuses to overwrite an existing directory.

```text
python -m backend.ml.context_curriculum
python -m backend.ml.train_context_transformer --curriculum --unitizer paragraphs-v2 --epochs 16 --output .models/context-transformer-curriculum-v2b --report evaluation/context-curriculum-training.json
python -m backend.ml.evaluate_context_transformer --model .models/context-transformer-curriculum-v2b --report evaluation/context-curriculum-results.json --fresh evaluation/context-promotion-check.json
```

Run export checks with `RUN_CURRICULUM_HEAD_TESTS=1` and the API stress checks
with `RUN_CONTEXT_STRESS_TESTS=1`:

```text
python -m pytest backend/tests/test_context_curriculum.py -q
```

CI checks the curriculum builder, source separation and passage boundaries.
GPU retraining and the candidate export checks remain local. Candidate weights,
cached source files and local account databases are ignored by Git; the source,
labels, provenance and result reports are committed. No public deployment is
part of this change.
