# Training with occupational tasks

This experiment adds real task descriptions to the earlier context classifier.
The balanced version makes fewer unsupported suggestions on the new benchmark,
but it misses too many skills on other checks. It is not loaded by the website.
The existing phrase extractor and sentence encoder are unchanged.

## Where the examples came from

The [dataset](../evaluation/context-source-cases.json) contains 748 base examples:
531 training, 134 development and 83 test examples. Of these, 437 are task
statements from the [O*NET 31.0 task-to-activity file](https://www.onetcenter.org/dictionary/31.0/csv/tasks_to_dwas.html).
The rest are project examples and short paraphrases of public descriptions.
O*NET supplies the task-to-activity relationships. The mapping from those
activities to CareerLens capabilities is a project decision, not an official
O*NET skill annotation.

The mapping covers 37 activities and initially supplied 467 tasks after split
checks. Checking the task wording against the proposed labels produced
64 changes in the [label audit](../evaluation/context-source-label-audit.json):
30 exclusions and 34 corrections. For example, answering a question does not
necessarily involve writing, and testing a program is different from developing
it. Remaining activity-based labels are still weak supervision: they may omit
other valid skills, and there has been no independent annotation review.

Public descriptions include a [controller role](https://jobs.smartrecruiters.com/CFOSuite/109569173-controller),
an [Indeed sales administrator listing](https://www.indeed.com/viewjob?jk=d04ac5ef82986fb4)
and a [LinkedIn property-software role](https://www.linkedin.com/jobs/view/yardi-genesis-wizard-at-jmr-associates-llc-4412901621).
They use language about multiple hats, an operational heartbeat and a software
wizard. Their concrete duties supply the useful context. An
[employee review](https://www.glassdoor.com/Reviews/Employee-Review-CustomerHD-E2510681-RVW78200835.htm)
is included as commentary, not as a vacancy. All four sources are test-only.
Expired but readable listings are marked as such; their availability is not
assumed. Only brief paraphrases are stored, without profiles or contact details.

An [additional check](../evaluation/context-final-check.json) contains 12
paraphrases from three more sources: Zoox, Ampd Energy and MongoDB. These were
collected after the two training configurations were fixed. They include
indirect duties, ordinary requirements, company background and benefits.
A redirected listing and a page that could not be retrieved were excluded.

## Splits and spelling

Occupations are assigned reproducibly to train, development or test before
augmentation. A task shared across different splits is removed. The builder
also removes cross-split pairs with token-set similarity of at least 0.8.
This removed six duplicate groups and eight near-duplicate rows. It reduces
leakage but cannot prove that every semantic paraphrase is separate.
All examples from the same public page stay together. Unmapped occupational
tasks are excluded; they are not assumed to be negative examples.

The previous training and development sentences retain their splits. The
earlier 56 test examples and 54 regression cases are not added to training.
They remain regression checks because their results are already known.

Deletion, transposition, duplication, joined words, broken spacing and casing
variants produce 4,965 inputs: 3,526 training, 885 development and 554 test.
These are related variants of 748 examples, not thousands of separate postings.
The extra three-source check has 80 variants of its 12 examples. Casing is valid
text; it is never suggested as a spelling correction merely for being uppercase.

## Training

The frozen MiniLM encoder supplies 384-dimensional vectors. Ridge regression
fits 9,240 weights and biases for the 24 supported capabilities. Expected and
acceptable training labels are both positive targets, so a defensible
alternative is not accidentally trained as a negative. Evaluation still counts
expected-label coverage separately from accepted-label precision.

Two versions use the same data and development search. The uniform version
weights each input equally. The balanced version weights rare capabilities
using training frequencies, with a separate weight for negative examples.
Both select regularization 1 and threshold 0.55 from development data. Neither
threshold is a probability. The encoder is not fine-tuned in this experiment.

## Results and decision

On the 554 new test inputs, including spelling variants:

| Method | Accepted-label precision | Expected-label coverage | Negative inputs with suggestions |
| --- | --- | --- | --- |
| Current context review | 74.39% | 40.68% | 3 / 108 |
| Source-trained, uniform weights | 93.22% | 34.96% | 3 / 108 |
| Source-trained, balanced weights | 94.74% | 41.95% | 0 / 108 |

The aggregate improvement does not hold everywhere. On 83 clean examples,
balanced-model coverage is 42.25%, compared with 43.66% for current review.
On the earlier 54 regression cases it falls from 85.11% to 59.57%, and one
negative case gains a suggestion. On the previous 365 spelling variants,
coverage falls from 56.80% to 40.29%, with nine negative-case errors.

The additional three-source check is especially useful: the balanced model
finds only 7 of 82 expected labels across 80 variants (8.54% coverage), compared
with 46 for current review (56.10%). Its seven suggestions agree with the
annotations, but that is far too little coverage to call it accurate overall.
On clean text it finds only one of 12 expected labels. The model has learned
some task patterns but does not generalize well enough to these descriptions.

Both candidates fail the release gates. The gates require at least 90%
precision, no loss of coverage and no additional negative-case errors against
current review, including earlier regressions and separate source slices.
The extra source check is an additional reason not to release them. No test
labels or thresholds were changed in response to its predictions.

These numbers measure agreement with project annotations, not independently
verified job-market accuracy. Related typo variants must not be treated as
independent observations. The next useful step is to obtain independently
reviewed descriptions with duty-level labels and explicit nonrequirements.
Simply adding more task sentences is unlikely to fix the domain difference.

Full predictions are in the [uniform report](../evaluation/context-source-results.json),
[balanced report](../evaluation/context-source-balanced-results.json) and
[additional source report](../evaluation/context-final-results.json).

## Reproduction

After installing the development requirements and the local sentence encoder:

```text
python -m backend.ml.context_source_data --download
python -m backend.ml.train_context_review --data evaluation/context-source-cases.json --output .models/context-head-source-v4 --report evaluation/context-source-results.json --previous-test evaluation/context-training-cases.json
python -m backend.ml.train_context_review --data evaluation/context-source-cases.json --output .models/context-head-source-balanced-v4 --report evaluation/context-source-balanced-results.json --previous-test evaluation/context-training-cases.json --balance-labels
python -m backend.ml.evaluate_context_heads
```

Use fresh output directories for another run. Manifests record source-data and
weight checksums, encoder revision, thresholds and training settings. The
source download has a pinned checksum. The separate Context training workflow
rebuilds the corpus, trains both versions, verifies exported predictions and
saves reports and weights as a 14-day artifact. It does not deploy them.

Set `RUN_SOURCE_HEAD_TESTS=1` to check both exported heads locally. Set
`RUN_CONTEXT_STRESS_TESTS=1` to send all 634 new test variants through the real
preview pipeline and exercise PDF, PNG, JPEG and WebP import. These software
checks cover response validity, evidence offsets, casing checks and score
separation. They do not prove that every extracted skill is correct.

The conversational-heading fixture imports automatically as PDF, PNG and WebP.
Its compressed JPEG loses spaces in both a duty and a heading, so that test
explicitly corrects the preview before analysis. The full reading is preserved;
this is a tested recovery path, not a claim of successful automatic recognition.

## Attribution

A later [duty-classifier follow-up](context-duty-training.md) adds seven employer
sources, preserves complete sentence context and fine-tunes encoder layers.
Its reports retain the earlier benchmarks as regressions.

This project includes information from the
[O*NET® 31.0 Database](https://www.onetcenter.org/database.html), by the U.S.
Department of Labor, Employment and Training Administration (USDOL/ETA), under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). O*NET® is a trademark
of USDOL/ETA. CareerLens selects tasks, maps activities to its capabilities,
corrects some labels and adds spelling variants. USDOL/ETA has not approved,
endorsed or tested these modifications. The crosswalk, task identifiers and
label audit record these changes.
