"""Keep common multiword qualities intact in source-aligned review results."""

import re
from backend.app.services.job_document import heading_kind

# These are explicit phrases, not inferred requirements. Joined misspellings are
# handled separately and always require review.
PHRASES = (
    "hard worker", "hard working", "team worker", "team player",
    "problem solving", "critical thinking", "creative thinking",
    "attention to detail", "time management", "active listening",
    "conflict resolution", "decision making", "customer service",
    "public speaking", "self motivated", "detail oriented",
)
PATTERN = re.compile(r"(?<!\w)(?:" + "|".join(
    r"[\s\-]+".join(map(re.escape, phrase.split())) for phrase in PHRASES
) + r")(?!\w)", re.IGNORECASE)


def preserve_phrases(text: str, spans: list[dict]) -> list[dict]:
    result = list(spans)
    for match in PATTERN.finditer(text):
        # Avoid adding a phrase from an explicitly denied or unrelated section.
        left = max(text.rfind(".", 0, match.start()), text.rfind(";", 0, match.start()), text.rfind("\n", 0, match.start())) + 1
        prefix = text[left:match.start()]
        if re.search(r"\b(?:no|not|never|without|don't|doesn't|isn't|isnt)\b", prefix, re.I):
            continue
        section = None
        line_start = text.rfind("\n", 0, match.start()) + 1
        for line in text[:line_start].splitlines():
            kind, _, _ = heading_kind(line)
            if kind:
                section = kind
        if ":" in text[line_start:match.start()]:
            kind, _, _ = heading_kind(text[line_start:match.start()])
            if kind:
                section = kind
        if section == "other":
            continue
        overlaps = [s for s in result if s["start"] < match.end() and match.start() < s["end"]]
        if any(s["start"] <= match.start() and s["end"] >= match.end() for s in overlaps):
            continue
        if any(s["start"] < match.start() or s["end"] > match.end() for s in overlaps):
            continue
        # Preserve normal narrative behaviour; expand partial model detections,
        # or recover an explicitly stated work quality in a requirement/list.
        if not overlaps and re.search(r"\b(?:our|his|her|their|offers?|provides?)\b", prefix, re.I):
            continue
        result = [s for s in result if s not in overlaps]
        result.append({"text": match.group(), "label": "skill", "start": match.start(), "end": match.end()})
    return sorted(result, key=lambda s: (s["start"], s["end"], s["label"]))
