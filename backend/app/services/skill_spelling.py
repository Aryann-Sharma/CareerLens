"""Explain known spelling corrections and offer uncertain matches for review."""

from functools import lru_cache
import re

from backend.app.services.skill_extractor import ALIAS_NAMES, EXTRACTION_PATTERN


# Explicit misspellings only. General edit-distance matches require confirmation.
COMMON_TYPOS = {
    "pyhton": "Python", "pythn": "Python", "pythno": "Python",
    "javascrip": "JavaScript", "javscript": "JavaScript", "javascritp": "JavaScript",
    "typescrip": "TypeScript", "typscript": "TypeScript", "typescritp": "TypeScript",
    "postgress": "PostgreSQL", "postgressql": "PostgreSQL", "postgreql": "PostgreSQL",
    "dokcer": "Docker", "dcoker": "Docker", "djagno": "Django",
    "kubernets": "Kubernetes", "kuberentes": "Kubernetes", "kubernetis": "Kubernetes",
    "fatapi": "FastAPI", "fastpai": "FastAPI", "linxu": "Linux", "lniux": "Linux",
}
TOKEN = re.compile(r"(?<![\w.+#-])[A-Za-z]+(?:\.[A-Za-z]+)?(?![\w+#-])")
FUZZY_ALIASES = {alias: name for alias, name in ALIAS_NAMES.items() if alias.isalpha() and len(alias) >= 5}


def one_edit_apart(left: str, right: str) -> bool:
    """One insertion, deletion, substitution, or adjacent transposition."""
    if abs(len(left) - len(right)) > 1 or left == right:
        return False
    if len(left) == len(right):
        differences = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        return len(differences) == 1 or (
            len(differences) == 2 and differences[1] == differences[0] + 1
            and left[differences[0]] == right[differences[1]]
            and left[differences[1]] == right[differences[0]]
        )
    shorter, longer = sorted((left, right), key=len)
    index = next((i for i, (a, b) in enumerate(zip(shorter, longer)) if a != b), len(shorter))
    return shorter[index:] == longer[index + 1:]


@lru_cache(maxsize=4096)
def candidates(word: str) -> tuple[str, ...]:
    word = word.casefold()
    if word in ALIAS_NAMES or not word.isalpha() or not 5 <= len(word) <= 24:
        return ()
    return tuple(sorted({name for alias, name in FUZZY_ALIASES.items() if one_edit_apart(word, alias)}))


def spelling_checks(text: str) -> list[dict]:
    checks = []
    seen = set()
    known_names = iter(EXTRACTION_PATTERN.finditer(text))
    known = next(known_names, None)
    for match in TOKEN.finditer(text):
        while known is not None and known.end() <= match.start():
            known = next(known_names, None)
        # A word inside a valid alias such as "POSTGRE SQL" is not a typo.
        if known is not None and known.start() <= match.start() and match.end() <= known.end():
            continue
        original = match.group()
        key = original.casefold()
        if key in seen or key in ALIAS_NAMES:
            continue
        seen.add(key)
        correction = COMMON_TYPOS.get(key)
        suggestions = [correction] if correction else list(candidates(key))
        if suggestions:
            checks.append({"original": original, "candidates": suggestions, "applied": bool(correction),
                           "start": match.start(), "end": match.end()})
        if len(checks) == 200:
            break
    return checks


def correct_known_typos(text: str) -> str:
    return TOKEN.sub(lambda match: COMMON_TYPOS.get(match.group().casefold(), match.group()), text)
