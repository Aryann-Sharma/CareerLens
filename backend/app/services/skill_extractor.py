import re

# Add new skills and their aliases here.
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
        rf"(?<!\w){re.escape(alias)}(?!\w)", re.IGNORECASE
    )


ALIAS_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    canonical: tuple(_alias_pattern(alias) for alias in aliases)
    for canonical, aliases in SKILL_ALIASES.items()
}

ALIAS_NAMES = {
    alias.casefold(): canonical
    for canonical, aliases in SKILL_ALIASES.items()
    for alias in aliases
}
# Match once from left to right, trying longer aliases first at each position.
# This keeps React.js and Postgre SQL from also matching their shorter parts.
EXTRACTION_PATTERN = re.compile(
    r"(?<!\w)(?:"
    + "|".join(re.escape(alias) for alias in sorted(ALIAS_NAMES, key=len, reverse=True))
    + r")(?!\w)",
    re.IGNORECASE,
)


def extract_skills(text: str) -> list[str]:
    """Return recognised skills once, ordered by their first appearance."""
    if not text or not text.strip():
        return []

    ordered_skills: list[str] = []
    for match in EXTRACTION_PATTERN.finditer(text):
        canonical = canonicalize_skill(match.group())
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
