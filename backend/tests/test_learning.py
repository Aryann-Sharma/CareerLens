import random
from urllib.parse import urlparse

import pytest

from backend.app.services.learning import DIRECTIONS, GUIDES, build_plan, get_guide
from backend.app.services.skill_extractor import SKILL_ALIASES


@pytest.mark.parametrize("skill", list(GUIDES))
def test_every_catalog_skill_has_a_complete_guide_and_acyclic_path(skill):
    assert set(GUIDES) == set(SKILL_ALIASES)
    item = get_guide(skill.swapcase())
    assert item["skill"] == skill
    assert item["available"] and len(item["milestones"]) == 3
    assert item["project"] and item["checked_on"] == "2026-10-13"
    assert all(urlparse(link["url"]).scheme == "https" for link in item["resources"])
    steps = build_plan([skill], [], None)["steps"]
    positions = {row["skill"]: index for index, row in enumerate(steps)}
    for row in steps:
        for prerequisite in row["prerequisites"]:
            assert positions[prerequisite] < positions[row["skill"]]


@pytest.mark.parametrize("direction", list(DIRECTIONS))
def test_role_additions_are_separate_from_requirements(direction):
    result = build_plan(["Java"], [], direction)
    assert next(step for step in result["steps"] if step["skill"] == "Java")["reason"] == "From your analysis"
    assert all(step["reason"] != "From your analysis" for step in result["steps"] if step["skill"] != "Java")
    assert "fit score" in result["notice"]


def test_plan_deduplicates_aliases_skips_known_skills_and_preserves_requirement_reasons():
    steps = build_plan(["react.js", "REACT", "CSS", "js"], ["html5", "javascript"], "web")["steps"]
    assert [row["skill"] for row in steps] == ["CSS", "React", "Git"]
    assert [row["reason"] for row in steps] == ["From your analysis", "From your analysis", "Suggested for your direction"]


@pytest.mark.parametrize("text", ["passionate", "goodlooking", "C++", "Rust", "编程", "<script>alert(1)</script>"])
def test_unknown_phrase_never_invents_a_course_or_changes_wording(text):
    result = get_guide(text)
    assert result["skill"] == text
    assert result["available"] is False
    assert result["resources"] == []


@pytest.mark.parametrize("typo,expected", [("PYHTON", "Python"), ("Pythom", "Python"), ("Reactt", "React"), ("javascrip", "JavaScript")])
def test_typo_offers_guide_choice_without_silent_replacement(typo, expected):
    result = get_guide(typo)
    assert result["skill"] == typo and not result["available"]
    assert expected in result["suggestions"]


def test_seeded_mixed_inputs_remain_unique_ordered_and_do_not_mutate_inputs():
    rng = random.Random(20261013)
    skills = list(GUIDES) + ["communication", "Pythom", "C++", "🌿"]
    for _ in range(80):
        missing, known = rng.sample(skills, 8), rng.sample(skills, 4)
        original = missing.copy()
        result = build_plan(missing, known, rng.choice([None, *DIRECTIONS]))
        names = [row["skill"].casefold() for row in result["steps"]]
        assert len(names) == len(set(names))
        assert not set(names).intersection(skill.casefold() for skill in known)
        assert missing == original


def test_public_learning_does_not_require_an_account_or_change_analysis(client):
    payload = {"job_description": "Web developer: good at programming", "user_skills": [], "extraction_method": "catalog"}
    before = client.post("/api/preview", json=payload).json()
    assert before["extracted_skills"] == []
    plan = client.post("/api/learning/plan", json={"missing_skills": [], "direction": "web"})
    assert plan.status_code == 200
    assert plan.headers["cache-control"] == "no-store"
    assert [step["skill"] for step in plan.json()["steps"]] == ["HTML", "CSS", "JavaScript", "Git"]
    assert client.post("/api/preview", json=payload).json() == before
    assert len(client.get("/api/learning/directions").json()) == 6


@pytest.mark.parametrize("body", [
    {"missing_skills": ["x"] * 201}, {"missing_skills": ["x" * 101]},
    {"missing_skills": [], "user_skills": ["x" * 101]},
    {"missing_skills": [], "direction": "invented"}, {"missing_skills": [], "extra": True},
    {"missing_skills": [123]},
])
def test_invalid_plan_inputs_are_rejected(client, body):
    assert client.post("/api/learning/plan", json=body).status_code == 422


def test_empty_plan_and_guide_limits(client):
    assert client.post("/api/learning/plan", json={"missing_skills": [" "]}).json()["steps"] == []
    assert client.get("/api/learning/guide", params={"skill": " "}).status_code == 422
    assert client.get("/api/learning/guide", params={"skill": "x" * 101}).status_code == 422
    response = client.get("/api/learning/guide", params={"skill": "java"})
    assert response.status_code == 200 and response.json()["skill"] == "Java"
    assert response.headers["cache-control"] == "no-store"
