# Local semantic matching

CareerLens uses a pretrained sentence encoder to compare short descriptions of
skills. It keeps exact matching as a baseline and shows which additional matches
came from similarity. This encoder's weights have not been fine-tuned. A separate
[fine-tuned DistilBERT extractor](contextual-model.md) supplies skill phrases for
analysis. This document describes the separate semantic matching stage.

## Model and runtime

- Encoder: `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional embeddings).
- Runtime: FastEmbed with ONNX Runtime on CPU, using two inference threads.
- Weight source: `qdrant/all-MiniLM-L6-v2-onnx`.
- Pinned revision: `d13954661f83248295ba75c1ed411eef3b7b936e`.
- Upstream model license: Apache 2.0.

The [upstream model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
describes its training and intended use. The
[runtime documentation](https://qdrant.github.io/fastembed/Getting%20Started/)
covers local embedding inference. This project uses an existing pretrained model;
it does not claim to have trained MiniLM.

## Setup

```text
python -m pip install -r backend/requirements.txt
python -m backend.scripts.download_model
python -m alembic upgrade head
```

The setup command downloads roughly 90 MB of weights and tokenizer files to
`.models/minilm`. Set `SEMANTIC_MODEL_PATH` to use another directory. Files stay
outside version control. The application only loads local files: a user request
never starts a download or sends skill text to a model provider.

## Pipeline

1. Receive the trained, catalog-only, or user-reviewed job-skill list.
2. Match exact user-entered skill names and aliases first.
3. Encode the remaining user phrases and compare them with one description per
   supported skill using cosine similarity.
4. Rank against the whole catalog, rather than only the current job's skills.
5. Accept the best skill only if similarity is at least **0.70**, the lead over
   the runner-up is at least **0.08**, and that skill is required by this job.
6. Save the score, exact baseline, model revision, thresholds, and original
   phrases used for suggested matches.

Known skills are not converted into different technologies. Java cannot become
JavaScript just because the names are related. Obvious denials containing words
such as “not,” “never,” or “without” are excluded from semantic suggestions.
This is a conservative guard, not complete negation understanding.

Semantic suggestions cover only the 18 catalog skills. Other phrases from
trained extraction or review use exact case-insensitive matching. The fixture
results below do not validate arbitrary phrase equivalence.

The 100-character limit on each user skill keeps inputs short. The complete job
description is not embedded or silently truncated; it goes through the existing
extractor. Exact skill profiles and empty comparisons do not need model inference.

Both modes calculate the fraction of detected job skills matched. Semantic mode
includes accepted suggestions in that fraction; it also displays the exact score.
Cosine similarity is a measure of embedding proximity, not a confidence percentage
or proof that the user has a skill. Scores are not hiring recommendations.

## Development evaluation

Run:

```text
python -m backend.scripts.evaluate_matching
```

The input is `evaluation/skill_phrases.jsonl`: 72 hand-authored examples, divided
into 36 calibration and 36 evaluation cases. Each has an expected catalog skill
or `null` when the system should abstain. These are development fixtures from the
same implementation work, not independently annotated real job data or an
untouched external benchmark. Some phrases resemble catalog descriptions.

The report includes model revision, a normalized dataset hash, precision, recall,
F1, every incorrect prediction, and a threshold sweep on the calibration split.
A wrong skill counts as both a false positive and a false negative. Abstaining
on a labelled skill counts as a false negative. Correct `null` predictions count
toward the total correct count but not skill precision or recall.

At the checked-in threshold, the evaluation fixtures produced:

| Method | Correct cases | Skill precision | Skill recall | F1 |
| --- | --- | --- | --- | --- |
| Exact baseline | 20 / 36 | 1.0000 | 0.3333 | 0.5000 |
| Semantic matching | 35 / 36 | 1.0000 | 0.9583 | 0.9787 |

The calibration sweep favored 0.70 as the lowest tested threshold with no false
positive skill predictions on that split. Lower thresholds improved recall but
incorrectly associated generic web development with a specific framework.
The resulting system still misses some valid paraphrases, including one CSS
description in the evaluation fixtures. These numbers only demonstrate behavior
on this small set; they should not be presented as general model accuracy.

## Future semantic-matching fine-tuning

Before fine-tuning the sentence encoder, collect licensed or consented examples from real
skill descriptions. Label equivalent, related-but-not-equivalent, ambiguous, and
unrelated phrase pairs. Include difficult negatives such as Java/JavaScript,
Docker/Kubernetes, and SQL/database products.

Split by original source or job posting before creating paraphrases, so near
duplicates cannot leak across training, validation, and test sets. Reserve an
independent test set, fine-tune only on training data, choose thresholds on
validation data, and compare against this frozen baseline. Report per-skill
precision, recall, abstentions, latency, and model size. Export and version the
resulting weights only if the evaluation supports using them.

The [Sentence Transformers training guide](https://sbert.net/docs/sentence_transformer/training_overview.html)
describes the supported fine-tuning workflow. The current fixtures are too small
and too close to the implementation to support a credible training claim.
