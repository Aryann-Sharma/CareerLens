"""Conservative boundaries between a duty and commentary about a workplace."""

import re

NEGATIVE = re.compile(r"\b(?:no|not|never|without|unnecessary|unneeded|isn't|isnt|don't|dont|doesn't|doesnt)\b", re.I)
# These modifiers do not deny the action. Any other denial in the sentence
# remains in place, including 'not required to work without supervision'.
POSITIVE_MODIFIER = re.compile(
    r"\bnot\s+(?:only|just)\b|\bwithout\s+(?:close\s+|constant\s+|direct\s+)?supervision\b"
    r"|\bwithout\s+being\s+asked\b", re.I)
COMMENTARY = re.compile(
    r"^\s*(?:an?|the)\s+(?:(?:former|current)\s+)?employee\s+"
    r"(?:review\s+(?:says|claims|reports|complains|jokes)|says|claims|reports|complains|jokes|mocks)\b", re.I)
BENEFIT = re.compile(r"^\s*(?:our\s+)?(?:benefits?|perks?)\s+(?:include|offer|provide)\b", re.I)


def denied_duty(text: str) -> bool:
    return bool(NEGATIVE.search(POSITIVE_MODIFIER.sub('', text)))


def workplace_commentary(text: str) -> bool:
    """Exclude explicit reports and benefits, not arbitrary humorous wording."""
    return bool(COMMENTARY.search(text) or BENEFIT.search(text))
