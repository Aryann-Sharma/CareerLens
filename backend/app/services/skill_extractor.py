import re

# Keep the MVP vocabulary deliberately small. New skills can be added here
# without changing the extraction algorithm.
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Docker": ("docker",),
    "FastAPI": ("fastapi", "fast api"),
    "Git": ("git",),
    "Java": ("java",),
    "JavaScript": ("javascript", "js", "ecmascript"),
    "Linux": ("linux",),
    "PostgreSQL": ("postgresql", "postgres", "postgre sql"),
    "Python": ("python",),
    "React": ("react", "react.js", "reactjs"),
    "SQL": ("sql",),
}


def _alias_pattern(alias: str) -> re.Pattern[str]:
    """Create boundaries that also work for names containing punctuation."""
    return re.compile(
        rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", re.IGNORECASE
    )


ALIAS_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    canonical: tuple(_alias_pattern(alias) for alias in aliases)
    for canonical, aliases in SKILL_ALIASES.items()
}


def extract_skills(text: str) -> list[str]:
    """Return recognised skills once, ordered by their first appearance."""
    if not text or not text.strip():
        return []

    candidates: list[tuple[int, int, str]] = []
    for canonical, patterns in ALIAS_PATTERNS.items():
        for pattern in patterns:
            candidates.extend(
                (match.start(), match.end(), canonical)
                for match in pattern.finditer(text)
            )

    # Prefer the longest overlapping phrase: "React.js" should produce React,
    # not both React and the shorter "js" alias for JavaScript.
    selected: list[tuple[int, int, str]] = []
    for start, end, canonical in sorted(
        candidates, key=lambda item: (-(item[1] - item[0]), item[0])
    ):
        overlaps = any(
            start < selected_end and end > selected_start
            for selected_start, selected_end, _ in selected
        )
        if overlaps:
            continue
        selected.append((start, end, canonical))

    ordered_skills: list[str] = []
    for _, _, canonical in sorted(selected, key=lambda item: item[0]):
        if canonical not in ordered_skills:
            ordered_skills.append(canonical)

    return ordered_skills


def canonicalize_skill(skill: str) -> str:
    """Map an exact user-entered alias to its canonical display name."""
    candidate = skill.strip()
    for canonical, patterns in ALIAS_PATTERNS.items():
        if any(pattern.fullmatch(candidate) for pattern in patterns):
            return canonical
    return candidate
