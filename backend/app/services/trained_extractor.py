"""Dispatch verified local extraction models and prepare reviewable skill lists."""

import json
import re
from pathlib import Path

from backend.ml.predict import ExtractorUnavailableError, extract as extract_crf
from backend.app.services.skill_extractor import canonicalize_skill, extract_skills
from backend.app.services.skill_spelling import correct_known_typos


# Reject fragments made entirely of grammar words, not words inside real phrases.
# Keep this conservative: short names such as C, R, Go, and IT are valid skills.
FUNCTION_WORDS = frozenset("""
a an the and or but nor to of in on at by for from with without into onto
be being been is are was were am have has had do does did
will would shall should can could may might must
you your yours we our ours they their theirs he she his her hers
this that these those which who whom whose as than then if so such
""".split())


def usable_skill_spans(spans: list[dict]) -> list[dict]:
    """Drop obvious prediction fragments without rewriting phrases or offsets."""
    usable = []
    for span in spans:
        value = " ".join(span["text"].split())
        words = re.findall(r"[^\W_]+", value, flags=re.UNICODE)
        if len(value) <= 100 and any(
            any(char.isalpha() for char in word) and word.casefold() not in FUNCTION_WORDS
            for word in words
        ):
            usable.append(span)
    return usable


def extract(text: str, model_path: Path, *, review_context: bool = False) -> dict:
    try:
        version = json.loads((model_path / "manifest.json").read_text())["format_version"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ExtractorUnavailableError("The extraction model is unavailable") from error
    if version == 2:
        from backend.ml.contextual_predict import extract as extract_contextual, extract_fragments
        prediction = extract_contextual(text, model_path)
        if review_context:
            from backend.app.services.span_context import merge_context_spans, review_fragments
            original = usable_skill_spans(prediction["spans"])
            fragments = review_fragments(text, original)
            if fragments:
                contextual = extract_fragments(text, fragments, model_path)
                prediction["spans"] = merge_context_spans(text, original, usable_skill_spans(contextual["spans"]), fragments)
        return prediction
    if version == 1:
        return extract_crf(text, model_path)
    raise ExtractorUnavailableError("Unsupported extraction model format")


def extract_for_review(text: str, model_path: Path) -> dict:
    return extract(text, model_path, review_context=True)


def suggested_skills(text: str, spans: list[dict]) -> list[str]:
    # Preserve named technologies even when the tagger predicts a wider activity.
    skills = extract_skills(correct_known_typos(text))
    seen = {skill.casefold() for skill in skills}
    for span in usable_skill_spans(spans):
        value = canonicalize_skill(correct_known_typos(" ".join(span["text"].split())))
        if value and len(value) <= 100 and value.casefold() not in seen:
            skills.append(value)
            seen.add(value.casefold())
    return skills[:200]
