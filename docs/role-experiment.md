# Occupation classification experiment

This is a completed offline experiment, not a feature used to choose learning
directions. Its results were too weak to justify automatic recommendations.
The app still uses the existing fine-tuned skill extractor and pretrained
semantic matcher; neither model was retrained in this experiment.

## Data and labels

The source is the [O*NET 31.0 Database](https://www.onetcenter.org/database.html).
Official occupation codes label titles, task statements, and occupation
descriptions. A documented mapping groups selected codes into data, database,
infrastructure, software, and web categories; remaining codes map to `other`.
These are occupation-labelled records, **not human-labelled job advertisements**.

`backend/ml/role_data.py` pins SHA-256 digests for four public CSV files. Only
`occupation_data.csv`, `job_titles.csv`, and `task_statements.csv` supply training
examples. `software_skills.csv` was downloaded for reference and is not a
training input. See the [source attribution](third-party/ONET-ATTRIBUTION.md).

Normalization removes case, spacing, and punctuation differences before
grouping. Conflicting groups with multiple target labels are excluded. A stable
group hash assigns roughly 70/20/10 percent to training/development/test. All
neighboring computing occupations are retained as negatives; other negative
examples are sampled reproducibly at one in twenty.

The audit found 64,017 normalized groups, 11,122 duplicate rows, and 114
conflicting groups. After filtering and negative sampling:

| Split | Records |
| --- | ---: |
| Training | 3,437 |
| Development | 1,025 |
| Test | 481 |

Exact normalized groups do not cross splits. Related title variants can still
cross splits. Most examples belong to `other`, and the test set contains only
one data-category example. This is not enough to estimate that category's
performance reliably. The evaluation is also from the same source as training.

## Training

The model is multinomial logistic regression with 8,192 hashed word and character
features. Character n-grams help retain partial evidence under spelling changes,
but do not guarantee typo resistance. PyTorch trains the linear layer's weights
and biases with weighted cross-entropy and AdamW; exported NumPy arrays support
offline inference without PyTorch.

The declared search used weight decay 0.001, 0.01, and 0.1, with checkpoints at
20, 40, 60, and 80 epochs. Development macro F1 selected weight decay 0.1 at
epoch 20. Acceptance thresholds and margins were also selected on development
data. The test split was evaluated only after those choices, without tuning on
its results. Seed: 42; feature version: `word-char-3-5-v1`.

## Results and decision

| Measure | Result |
| --- | ---: |
| Majority-class test accuracy | 91.27% |
| Model test accuracy | 92.52% |
| Development macro F1 | 53.30% |
| Test macro F1 | 49.46% |
| Test macro F1 with one prescribed word transposition | 34.20% |

The development gate accepted 12 examples with no mistakes. On test it accepted
only six examples and got one wrong: 83.33% precision at 1.25% coverage. These
small counts do not support a dependable recommendation feature. Overall
accuracy is misleading here because `other` dominates the data.

**Decision: do not connect this classifier to the app.** Learning directions
remain user-selected. The [complete report](../evaluation/role-results.json)
contains every checkpoint, class supports, precision/recall/F1, source hashes,
and the robustness check. The separate saved `weights.npz` and manifest are
local generated artifacts, excluded from version control.

A useful next experiment needs a larger, independently annotated collection of
real job postings with clear role definitions, enough examples per class, and
an external test set. Relabelling model guesses as ground truth or repeatedly
tuning on these test examples would not establish accuracy.

## Reproduce

Use the training environment described in [training.md](training.md), with
NumPy and PyTorch installed. Run from the repository root:

```powershell
python -m backend.ml.role_data --output .data/onet-31.0
python -m backend.ml.train_roles --output .models/onet-roles-new --report evaluation/role-results-new.json
```

The output directory must be new; the script refuses to overwrite weights.
Downloading data needs network access. Training and inference use local files.
The application does not load this artifact or require these data files.

To verify the original recorded experiment against the installed artifact:

```powershell
$env:RUN_ROLE_TESTS = '1'
python -m pytest backend/tests/test_role_experiment.py -q
```

This optional test expects `.data/onet-31.0`, `.models/onet-roles`, and the recorded
report. Ordinary tests use small controlled fixtures and never download data.
