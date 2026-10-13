# Reviewing the wider role context

Phrase extraction and interpreting a duty are different tasks. A span tagger can
find wording in a description without understanding what a joke is asking for.
For example, mediating between arguing departments can suggest conflict
resolution even when those exact words do not appear.

With **Find skills in context**, the browser now requests an additional review
under **Check the wider role context**. It offers up to six possible capabilities,
each with supporting text. Choose **Add** to put one in the skill editor, remove
literal or duplicate phrases, then choose **Update analysis**. **Dismiss** keeps
the current list. Suggestions alone never change the fit score, profile, or
learning roadmap. Saved analysis details retain the original suggestions.

## How it works

This uses the existing local MiniLM sentence encoder and 24 project-authored
capability descriptions, each with a second wording. It does not train new
weights or call a hosted service. The capability descriptions are reference
prototypes, not a labelled training dataset. They cover general activities such
as programming, debugging, teamwork, customer support, communication, planning,
and research. They do not infer a specific programming language or tool from a
broad role title.

The service splits the description into bounded passages and keeps their source
offsets. It excludes recognised benefits/company/application sections and
explicitly negated sentences. A pooled document view and neighbouring passages
provide broader context. For long descriptions, at most 48 passages are sampled
across the document, including its end. This is not a guarantee that every line
was considered.

The ranking combines local passage similarity (75%), neighbouring passage
similarity (15%), and pooled document similarity (10%). A candidate needs a score
of at least 0.43 (0.50 for debugging), local similarity of at least 0.40, and a
score within 0.04 of the best capability for that passage. Short slash-separated
job titles and labelled official titles cannot be the only supporting evidence.
Similarity scores are not probabilities and are not displayed as confidence.

API clients enable this with `interpret_duties: true` alongside
`extraction_method: "trained"` on `/api/preview` or `/api/analyze`. The default is
false for API compatibility. `extraction_details.context_suggestions` contains
the proposed skill, evidence, offsets and similarity; `context_notice` explains
the review requirement. A missing or busy sentence model leaves the normal
analysis available with an explanatory notice. User-reviewed lists are used
directly and do not run this step again. The raw `/api/extract` endpoint and
existing benchmark procedure remain unchanged.

## Evaluation and limits

A later [supervised context-head experiment](context-training.md) uses 242
distinct examples and 1,612 spelling/casing variants. It trains new head weights
and reports a clean-only control. It failed the replacement checks and remains
outside the application; the behaviour described here is still the live path.

The initial 32 project-authored examples include the reported descriptions,
plain duties, other humorous wording, and negative cases. Thresholds were
adjusted using these examples, so they are development results. The final run
produced 36 suggestions: 34 fell within the expected or acceptable labels. It
covered 30 of 32 expected labels. Errors included reading a database's metaphorical
coffee break as time management and suggesting negotiation for task allocation.

A further 22 cases were written after fixing those thresholds. On this small
check, all 11 returned suggestions were within the listed acceptable meanings,
but only 10 of 15 expected capabilities were found. Five expected capabilities
were missed. Neither set has independent expert annotations, and neither is a
representative accuracy benchmark. The complete cases, misses and extra
suggestions are committed rather than reporting only successful examples.

```text
python -m backend.scripts.evaluate_context
python -m backend.scripts.evaluate_context --cases evaluation/context-holdout.json --output evaluation/context-holdout-results.json
```

See [development results](../evaluation/context-results.json) and
[additional evaluation results](../evaluation/context-holdout-results.json).

This is conservative retrieval, not general sarcasm understanding. Negation,
irony, fictional statements, implied duties and unfamiliar occupations can still
be misunderstood or missed. A simple negation filter can also suppress a valid
requirement in a sentence containing a denial. Vague two-word actions with an unspecified object, such as “delete it”, are
filtered from review results. The phrase extractor may still return other literal fragments alongside better context suggestions; the editor is
where the user resolves them. Broadening automatic scoring needs independently
labelled job descriptions, including negative examples and disagreements about
meaning, plus a separate held-out evaluation. The current fixtures should not
be relabelled as public or human-annotated training data.

## Compound words

The review pipeline preserves 16 listed multiword workplace phrases, such as
hard worker, active listening, time management and attention to detail. It
combines contained token fragments while keeping the original source offsets.
It avoids adding phrases from recognised unrelated sections or explicit denials;
it does not remove every incorrect prediction made by the underlying tagger.

Spelling checks now consider joined compounds and a one-edit mistake inside
two- or three-word phrases. For example, `hardworker`, `team wokrer` and
`critical thinkng` offer review choices. Valid casing, hyphenation, common
single-word forms and plurals do not trigger those corrections. The original
text is preserved and uncertain corrections require confirmation.

This remains a bounded skill vocabulary, not a complete English spellchecker.
The browser's red underline comes from its own dictionary; it is independent
of the application's suggestions. Unknown words, several simultaneous mistakes,
and valid words used in the wrong context can still go unflagged.
