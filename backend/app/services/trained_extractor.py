"""Dispatch verified local extraction models and prepare reviewable skill lists."""

import json
from pathlib import Path

from backend.ml.predict import ExtractorUnavailableError, extract as extract_crf
from backend.app.services.skill_extractor import canonicalize_skill, extract_skills


def extract(text: str, model_path: Path) -> dict:
    try:
        version = json.loads((model_path / "manifest.json").read_text())["format_version"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ExtractorUnavailableError("The extraction model is unavailable") from error
    if version == 2:
        from backend.ml.contextual_predict import extract as extract_contextual
        return extract_contextual(text, model_path)
    if version == 1:
        return extract_crf(text, model_path)
    raise ExtractorUnavailableError("Unsupported extraction model format")


def suggested_skills(text: str, spans: list[dict]) -> list[str]:
    # Preserve named technologies even when the tagger predicts a wider activity.
    skills = extract_skills(text)
    seen = {skill.casefold() for skill in skills}
    for span in spans:
        value = canonicalize_skill(" ".join(span["text"].split()))
        if value and len(value) <= 100 and value.casefold() not in seen:
            skills.append(value)
            seen.add(value.casefold())
    return skills[:200]
