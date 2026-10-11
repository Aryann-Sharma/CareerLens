"""Suggest relevant sections while retaining the complete extracted document."""

import re
import unicodedata

ROLE_HEADINGS = {
    "job description", "role description", "role overview", "about the role",
    "the role", "your role", "position summary", "job summary", "overview",
    "responsibilities", "key responsibilities", "your responsibilities",
    "duties", "job duties", "duties and responsibilities",
    "roles and responsibilities", "what you will do", "what youll do",
    "what you will be doing", "requirements", "job requirements",
    "role requirements", "required skills", "skills", "skills and experience",
    "skills and qualifications", "qualifications", "required qualifications",
    "minimum qualifications", "preferred qualifications", "essential qualifications",
    "basic qualifications", "experience", "education", "education and experience",
    "essential skills", "technical skills", "preferred skills", "nice to have",
    "what you bring", "what youll bring", "what we are looking for",
    "what were looking for", "who you are", "about you", "what you need",
    "responsibilities and requirements", "requirements and qualifications",
}
OTHER_HEADINGS = {
    "about us", "about the company", "company overview", "company description",
    "our company", "who we are", "our mission", "our values", "our culture",
    "benefits", "perks", "perks and benefits", "benefits and perks",
    "what we offer", "what youll get", "why join us", "compensation",
    "salary", "salary and benefits", "compensation and benefits",
    "how to apply", "application process", "apply now", "application instructions",
    "equal opportunity", "equal opportunity employer", "equal opportunities",
    "privacy notice", "recruitment privacy notice",
}


def heading_kind(line: str) -> tuple[str | None, str, str]:
    raw = unicodedata.normalize("NFKC", line).strip()
    # Also accept numbered headings and headings followed by text on the same line.
    raw = re.sub(r"^[\s#*•\-–—\d.)]+", "", raw)
    title, separator, content = raw.partition(":")
    normalized = title.casefold().replace("&", "and")
    normalized = re.sub(r"['’]", "", normalized)
    normalized = re.sub(r"[\W_]+", " ", normalized).strip()
    if normalized in ROLE_HEADINGS:
        return "role", title.strip(), content.strip() if separator else ""
    if normalized in OTHER_HEADINGS:
        return "other", title.strip(), content.strip() if separator else ""
    # An unfamiliar heading ends an excluded section; keep its contents to avoid
    # silently losing requirements under uncommon headings.
    words = title.split()
    if 1 <= len(words) <= 8 and (raw.endswith(":") or title.isupper() or title.istitle() or line.lstrip().startswith("#")):
        return "unknown", title.strip(), content.strip()
    return None, "", ""


def prepare_job_document(text: str) -> dict:
    sections: list[tuple[str, str, list[str]]] = []
    kind, heading, lines = "unknown", "", []
    for line in text.splitlines(keepends=True):
        new_kind, title, _ = heading_kind(line)
        if new_kind:
            sections.append((kind, heading, lines))
            kind, heading, lines = new_kind, title, [line]
        else:
            lines.append(line)
    sections.append((kind, heading, lines))
    role_sections = [heading for kind, heading, lines in sections
                     if kind == "role" and (heading_kind(lines[0])[2] or "".join(lines[1:]).strip())]
    # No reliable role section means no automatic removal, including benefits-only pages.
    selected = "".join("".join(lines) for kind, _, lines in sections if kind != "other").strip()
    applied = bool(role_sections and any(kind == "other" for kind, _, _ in sections) and selected)
    return {
        "text": selected if applied else text,
        "full_text": text,
        "selected_sections": list(dict.fromkeys(role_sections)),
        "selection_applied": applied,
    }
