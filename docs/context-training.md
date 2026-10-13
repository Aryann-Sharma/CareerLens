# Training a context suggestion head

This experiment tests whether a small supervised model improves suggestions for
indirect duties and misspelled descriptions. It trains new weights, but does not
replace the model used by the website: the candidate failed the release checks.
The existing phrase extractor and sentence encoder have not been retrained.

## Data and sources

The [corpus](../evaluation/context-training-cases.json) contains 242 distinct
examples: 132 training, 54 development and 56 test examples. It covers the 24
capabilities supported by context review. Most sentences were written for this
project. There are also user-supplied titles and satirical descriptions, plus
five short paraphrases of public sources. The public-source and user examples
are test-only. They are not claimed to be verified LinkedIn posts unless the
source record establishes that.

The source records include access dates and distinguish:

- Two readable, expired LinkedIn listings: a backend engineering role using a
  data-herding metaphor and a Chief Meme Officer role with concrete duties.
- A LinkedIn editorial about a historical meme recruitment campaign.
- An Indeed project-coordinator listing excerpt using a connecting metaphor.
  Its detail page was unavailable, so only the accessible excerpt was used.
- A Glassdoor community discussion about job-advertising language. It is
  commentary, not a vacancy, and is a negative example.

An employer page returning 410 and a LinkedIn URL redirecting to an unrelated
search were excluded. Full posts, profiles and personal contact information
were not collected. Source paraphrases and skill labels are project judgements;
the employers did not provide annotations. These are not independently reviewed
gold labels or a representative sample of the job market.

Each case lists expected capabilities and defensible alternatives. A vague title,
salary statement or complaint can have an empty expected list. The task covers
only the 24 supported capabilities; other valid job requirements may be outside
that vocabulary. Some label boundaries, such as teamwork versus resolving a
team dispute, are subjective. Independent annotation is needed before treating
the reported precision as a reliable estimate for users.

## Spelling augmentation and split checks

The reproducible variants cover one deleted letter, adjacent-letter swaps,
duplicated letters, a missing word separator, an extra space inside a word and
uppercase text. Short negation words are protected. Unchanged variants are
removed. Casing is tested as valid text, not marked as a spelling mistake.

This produces 1,612 inputs: 886 training, 361 development and 365 test inputs.
These counts include related variants and must not be described as 1,612
independent job postings. Original texts and all their variants stay in one
split. Duplicate normalized text and shared families cannot cross splits.
The typo mutations are deliberately mild; this does not establish robustness to
several simultaneous errors or severe OCR damage.

## What is trained

The frozen local MiniLM encoder produces 384-dimensional sentence vectors.
Ridge regression learns a 384-by-24 weight matrix and 24 biases: 9,240 parameters
mapping those vectors to the supported capabilities. The training target has a
value of one for the expected labels and zero for other labels. Training cases
do not contain ambiguous alternative labels. Negative examples have all-zero
targets.

The development split selects among regularization values 0.1, 1 and 10, and
thresholds 0.25 through 0.75 in steps of 0.10. Selection favours candidates with
at least 90% development precision, then their F0.5 score. The selected augmented
model uses regularization 10 and threshold 0.25. Scores are regression outputs,
not probabilities. At evaluation, the existing passage-selection code keeps
source-aligned units; the highest passage score for each capability determines
whether it is suggested, up to six suggestions.

The test split does not choose parameters. The previous 54 context examples are
separate regression checks, not training data. A clean-only training control
uses the same development search and evaluation inputs. It is an ablation to
measure augmentation, not a second opportunity to select against test results.
The augmented run was repeated and reproduced identical weight and bias arrays.

## Results

On the 365 test inputs, counting related typo variants:

| Method | Accepted-label precision | Expected-label coverage | Negative inputs with suggestions |
| --- | --- | --- | --- |
| Existing context review | 72.19% | 56.80% | 0 / 141 |
| Head trained on clean sentences | 72.78% | 62.14% | 25 / 141 |
| Head trained with typo variants | 77.27% | 64.08% | 13 / 141 |

On the 56 clean test examples, the augmented head found 22 of 31 expected
capabilities, compared with 20 for the existing review. However, it suggested
negotiation for a salary complaint and empathy for a cynical morale description.
It also confused an invoice-software defect with attention to detail.

The previous 54 regression examples exposed another tradeoff: expected-label
coverage fell from 85.11% to 80.85%. This is why improved results on the new set
were not enough to replace the current implementation. Broken word spacing was
especially difficult: augmented-head coverage was 54.84% on that test slice,
compared with 70.97% on clean text.

The release rule requires at least 90% precision, no lower precision or coverage
than the baseline, and no additional negative-case errors on the full test set,
clean test set and previous regressions. Both trained candidates failed. Their
weights remain local experimental artifacts and are not loaded by the app.

See the [augmented report](../evaluation/context-training-results.json) and
[clean-only control](../evaluation/context-clean-control-results.json) for every
development configuration, each spelling slice, predictions, misses and extra
suggestions. Acceptable alternatives count toward precision; coverage counts
only expected labels. These metrics measure agreement with the project labels,
not hiring suitability or general language understanding.

## Reproduce

Install the normal application dependencies and local matching model first.
No additional training dependency or external inference service is required.
Choose new output directories: existing models are never overwritten.

```text
python -m backend.scripts.download_model
python -m backend.ml.train_context_review
python -m backend.ml.train_context_review --no-augmentation --output .models/context-head-clean-control --report evaluation/context-clean-control-results.json
```

Each output directory contains `weights.npz` and `manifest.json`. The manifest
records encoder revision, data checksum, weight checksum, threshold and training
configuration. NumPy fits the head on CPU; the encoder weights stay frozen.
On subsequent runs use `--output` with a fresh path. CI runs both experiments,
checks exported weights against the recorded clean test predictions, and keeps
the reports and model files as a 14-day artifact. It does not install either
experimental head in the application.

Enable the real-model workflow stress tests after setting up the contextual
extractor described in the [model guide](contextual-model.md):

```powershell
$env:RUN_CONTEXT_STRESS_TESTS = '1'
python -m pytest backend/tests/test_context_training.py -q
Remove-Item Env:RUN_CONTEXT_STRESS_TESTS
```

With the two default artifact directories present, set
`RUN_CONTEXT_HEAD_TESTS=1` to also verify their checksums, dimensions, encoder
revision and recorded clean-test predictions.

These checks send all 365 test variants through `/api/preview`, checking response
validity, evidence offsets, score consistency and separation of unconfirmed
suggestions. Twelve additional PDF/PNG/JPEG/WebP imports check that indirect and
misspelled text can reach analysis with source-aligned evidence. They do not
assert that OCR or skill interpretation is perfect. The model-quality reports
are separate from these software checks.

## What this does not solve

The live extractor can still emit literal fragments from sarcasm, and the
current context review can infer a duty from a complaint about managers. The
new tests record these limitations rather than treating every nonempty result
as correct. More copies or spelling mutations of the same sentences will not
fix that distinction. A stronger next dataset needs independently reviewed
duties, nonrequirements, negations and indirect language, with disagreements
resolved and whole source documents kept out of training for evaluation.
