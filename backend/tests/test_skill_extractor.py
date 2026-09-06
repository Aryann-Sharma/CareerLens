import pytest

from backend.app.services.skill_extractor import canonicalize_skill, extract_skills


def test_extracts_skills_in_order_of_first_appearance() -> None:
    text = "We need Python, SQL, React, Git and FastAPI."

    assert extract_skills(text) == ["Python", "SQL", "React", "Git", "FastAPI"]


def test_removes_duplicate_mentions() -> None:
    text = "Python developer using python and PYTHON every day."

    assert extract_skills(text) == ["Python"]


def test_matches_aliases_case_insensitively() -> None:
    text = "Experience with JS, postgres, and FAST API."

    assert extract_skills(text) == ["JavaScript", "PostgreSQL", "FastAPI"]


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Deploy services with Docker.", "Docker"),
        ("Build APIs using FastAPI.", "FastAPI"),
        ("Use Git for version control.", "Git"),
        ("Develop backend services in Java.", "Java"),
        ("Write browser logic in JavaScript.", "JavaScript"),
        ("Work comfortably in Linux.", "Linux"),
        ("Store relational data in PostgreSQL.", "PostgreSQL"),
        ("Automate workflows with Python.", "Python"),
        ("Build interfaces with React.", "React"),
        ("Write efficient SQL queries.", "SQL"),
    ],
)
def test_extracts_each_mvp_skill(description: str, expected: str) -> None:
    assert extract_skills(description) == [expected]


def test_does_not_match_skills_inside_other_words() -> None:
    text = "We value collaboration, reactiveness, and transcript review."

    assert extract_skills(text) == []


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_text_returns_no_skills(text: str) -> None:
    assert extract_skills(text) == []


def test_handles_skills_next_to_punctuation() -> None:
    text = "Required: Python/SQL; Git, Docker (Linux)."

    assert extract_skills(text) == ["Python", "SQL", "Git", "Docker", "Linux"]


def test_prefers_longest_overlapping_skill_name() -> None:
    assert extract_skills("React.js") == ["React"]


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("js", "JavaScript"),
        ("Postgres", "PostgreSQL"),
        (" fast api ", "FastAPI"),
        ("python", "Python"),
    ],
)
def test_canonicalizes_exact_aliases(alias: str, expected: str) -> None:
    assert canonicalize_skill(alias) == expected


def test_preserves_trimmed_unknown_user_skill() -> None:
    assert canonicalize_skill("  Rust  ") == "Rust"


def test_does_not_canonicalize_partial_alias() -> None:
    assert canonicalize_skill("JavaScript framework") == "JavaScript framework"
