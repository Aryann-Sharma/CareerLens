import pytest

from backend.app.services.scorer import analyze_skill_match
from backend.app.services.skill_extractor import extract_skills


def test_returns_the_expected_analysis() -> None:
    result = analyze_skill_match(
        ["Python", "SQL", "React", "Git", "FastAPI"],
        ["Python", "Java", "SQL", "Git"],
    )

    assert result == {
        "matched_skills": ["Python", "SQL", "Git"],
        "missing_skills": ["React", "FastAPI"],
        "match_score": 60,
    }


def test_scores_skills_returned_by_the_extractor() -> None:
    job_skills = extract_skills("We need Python, SQL, React, Git and FastAPI.")

    result = analyze_skill_match(job_skills, ["Python", "SQL", "Git"])

    assert result["matched_skills"] == ["Python", "SQL", "Git"]
    assert result["missing_skills"] == ["React", "FastAPI"]
    assert result["match_score"] == 60


@pytest.mark.parametrize(
    ("job_skills", "user_skills", "expected_score"),
    [
        (["Python"], ["Python"], 100),
        (["Python"], [], 0),
        (["Python", "SQL", "Git"], ["Python", "SQL"], 67),
        (["Python", "SQL", "React", "Git"], ["SQL"], 25),
    ],
)
def test_calculates_match_score(
    job_skills: list[str], user_skills: list[str], expected_score: int
) -> None:
    result = analyze_skill_match(job_skills, user_skills)

    assert result["match_score"] == expected_score


def test_matches_skills_case_insensitively() -> None:
    result = analyze_skill_match(["Python", "SQL"], ["PYTHON", "sql"])

    assert result["matched_skills"] == ["Python", "SQL"]
    assert result["missing_skills"] == []


def test_accepts_user_skill_aliases() -> None:
    result = analyze_skill_match(["JavaScript", "PostgreSQL"], ["js", "postgres"])

    assert result["matched_skills"] == ["JavaScript", "PostgreSQL"]
    assert result["match_score"] == 100


def test_ignores_duplicate_user_skills() -> None:
    result = analyze_skill_match(["Python", "SQL"], ["Python", "python", "PYTHON"])

    assert result["matched_skills"] == ["Python"]
    assert result["missing_skills"] == ["SQL"]
    assert result["match_score"] == 50


def test_ignores_blank_and_extra_user_skills() -> None:
    result = analyze_skill_match(
        ["Python", "Git"], ["", "   ", "Python", "Rust", "Kotlin"]
    )

    assert result["matched_skills"] == ["Python"]
    assert result["missing_skills"] == ["Git"]
    assert result["match_score"] == 50


def test_preserves_job_skill_order() -> None:
    result = analyze_skill_match(
        ["React", "Python", "Docker", "SQL"], ["SQL", "React"]
    )

    assert result["matched_skills"] == ["React", "SQL"]
    assert result["missing_skills"] == ["Python", "Docker"]


def test_returns_empty_result_when_no_job_skills_are_extracted() -> None:
    result = analyze_skill_match([], ["Python"])

    assert result == {
        "matched_skills": [],
        "missing_skills": [],
        "match_score": 0,
    }


def test_does_not_modify_input_lists() -> None:
    job_skills = ["Python", "SQL"]
    user_skills = ["Python"]

    analyze_skill_match(job_skills, user_skills)

    assert job_skills == ["Python", "SQL"]
    assert user_skills == ["Python"]
