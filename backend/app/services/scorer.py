from typing import TypedDict

from backend.app.services.skill_extractor import canonicalize_skill


class MatchResult(TypedDict):
    matched_skills: list[str]
    missing_skills: list[str]
    match_score: int


def analyze_skill_match(
    extracted_skills: list[str], user_skills: list[str]
) -> MatchResult:
    """Compare job skills with user skills and calculate a percentage score."""
    if not extracted_skills:
        return {
            "matched_skills": [],
            "missing_skills": [],
            "match_score": 0,
        }

    user_skills_normalized = {
        canonicalize_skill(skill).casefold() for skill in user_skills if skill.strip()
    }

    matched_skills: list[str] = []
    missing_skills: list[str] = []

    for skill in extracted_skills:
        if skill.casefold() in user_skills_normalized:
            matched_skills.append(skill)
        else:
            missing_skills.append(skill)

    match_score = round(len(matched_skills) / len(extracted_skills) * 100)

    return {
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "match_score": match_score,
    }
