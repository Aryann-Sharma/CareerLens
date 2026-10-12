"""Choose short skill fragments for a context pass and merge source-aligned spans."""

import re
from bisect import bisect_left

from backend.app.services.job_document import heading_kind
from backend.ml.predict import TOKEN_PATTERN

SKILL_HEADINGS = {
    "skills", "skills to build", "required skills", "technical skills",
    "essential skills", "preferred skills", "skills and experience",
    "skills and qualifications", "requirements", "job requirements",
    "qualifications", "required qualifications", "preferred qualifications",
    "minimum qualifications", "basic qualifications", "nice to have",
}
LIST_MARKER = re.compile(r"^\s*(?:[-*•–]\s+|\d+[.)]\s*)")
REQUIREMENT_LEAD = re.compile(
    r"(?:we\s+(?:want|need|require|seek|are\s+(?:looking\s+for|seeking))"
    r"|(?:you|candidates?|applicants?|the\s+successful\s+candidate)\s+"
    r"(?:must|should|need\s+to|needs\s+to|are\s+expected\s+to|is\s+expected\s+to|will\s+need\s+to)"
    r"\s+(?:be|have|demonstrate|possess|bring))\s+",
    re.IGNORECASE,
)
NEGATION = re.compile(r"\b(?:no|not|never|without|cannot|neither|nor)\b|n['’]t\b", re.IGNORECASE)


def requirement_fragments(text: str, start: int, end: int) -> list[dict]:
    """Recheck affirmative candidate requirements, retaining original offsets."""
    fragments = []
    clause_start = start
    # Token boundaries preserve names containing punctuation, such as Node.js.
    tokens = list(TOKEN_PATTERN.finditer(text, start, end))
    boundaries = [token for token in tokens if token.group() in {",", ";", ".", "!", "?"}]
    for clause_end, next_start in [(t.start(), t.end()) for t in boundaries] + [(end, end)]:
        while clause_start < clause_end and text[clause_start].isspace():
            clause_start += 1
        lead = REQUIREMENT_LEAD.match(text, clause_start, clause_end)
        if lead and not NEGATION.search(text, clause_start, clause_end):
            body = list(TOKEN_PATTERN.finditer(text, lead.end(), clause_end))
            if body and len(body) <= 16 and body[-1].end() - body[0].start() <= 100:
                fragments.append({"start": body[0].start(), "end": body[-1].end(), "allow_new": True})
        clause_start = next_start
    return fragments


def review_fragments(text: str, spans: list[dict]) -> list[dict]:
    """Review skill lists, explicit requirements, and clipped phrase boundaries."""
    fragments = []
    ordered = sorted(spans, key=lambda span: span["start"])
    starts = [span["start"] for span in ordered]
    in_skills = False
    in_other_section = False
    offset = 0
    for line in text.splitlines(keepends=True):
        start = offset
        offset += len(line)
        value = line.strip()
        if not value:
            in_skills = False
            continue
        kind, title, inline = heading_kind(line)
        normalized = re.sub(r"[\W_]+", " ", title.casefold().replace("&", "and")).strip()
        # This heading occurs in copied lists of previously extracted skills.
        if value.casefold().rstrip(":") == "skills to build":
            normalized, kind, inline = "skills to build", "role", ""
        if normalized in SKILL_HEADINGS:
            in_skills = True
            in_other_section = False
            if not inline:
                continue
            start += line.index(":") + 1
        elif kind in {"role", "other"} or value.endswith(":"):
            in_skills = False
            in_other_section = kind == "other"
            continue
        body = text[start:offset]
        marker = LIST_MARKER.match(body)
        if marker:
            start += marker.end()
        if not in_other_section:
            fragments.extend(requirement_fragments(text, start, offset)[:200 - len(fragments)])
        if len(fragments) == 200:
            break
        tokens = list(TOKEN_PATTERN.finditer(text, start, offset))
        if not tokens:
            continue
        start, end = tokens[0].start(), tokens[-1].end()
        # Other full sentences and long paragraphs retain their original inference.
        if end - start > 100 or len(tokens) > 16 or any(t.group() in {".", "!", "?", ";"} for t in tokens):
            continue
        local_spans = ordered[bisect_left(starts, start):bisect_left(starts, end)]
        can_extend = any(span["end"] < end and text[span["end"]:end].strip() for span in local_spans)
        if in_skills or can_extend:
            fragments.append({"start": start, "end": end, "allow_new": in_skills})
        if len(fragments) == 200:
            break
    return fragments


def merge_context_spans(text: str, original: list[dict], contextual: list[dict], fragments: list[dict]) -> list[dict]:
    merged = [dict(span) for span in original]
    for candidate in contextual:
        start, end = candidate["start"], candidate["end"]
        region = next((r for r in fragments if r["start"] <= start < end <= r["end"]), None)
        if region is None or candidate["text"] != text[start:end]:
            continue
        overlaps = [span for span in merged if span["start"] < end and start < span["end"]]
        if not overlaps:
            if region["allow_new"]:
                merged.append(candidate)
            continue
        # Extend one clipped phrase, without merging two requirements or replacing
        # a longer original span with a shorter contextual prediction.
        if len(overlaps) != 1:
            continue
        old = overlaps[0]
        if old["label"] != candidate["label"] or start != old["start"] or end <= old["end"]:
            continue
        tail = text[old["end"]:end]
        if re.search(r"[,;.!?\n]|\b(?:and|or)\b", tail, re.IGNORECASE):
            continue
        merged[merged.index(old)] = candidate
    return sorted(merged, key=lambda span: (span["start"], span["end"], span["label"]))
