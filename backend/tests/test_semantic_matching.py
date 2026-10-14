import os
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.services import semantic_matcher as matcher
from backend.app.services.skill_extractor import SKILL_ALIASES


def test_model_catalog_covers_the_extractor() -> None:
    assert set(matcher.SKILL_DESCRIPTIONS) == set(SKILL_ALIASES)


def test_semantic_matches_keep_exact_matches_and_explain_additions(monkeypatch) -> None:
    monkeypatch.setattr(matcher, "rank_skills", lambda phrases: [
        [("SQL", 0.85), ("PostgreSQL", 0.5)],
    ])
    result, details = matcher.analyze_semantic_match(
        ["Python", "SQL", "CSS"], ["Python", "writing database queries"],
    )
    assert result == {
        "matched_skills": ["Python", "SQL"], "missing_skills": ["CSS"], "match_score": 67,
    }
    assert details["exact_match_score"] == 33
    assert details["semantic_matches"] == [
        {"skill": "SQL", "user_skill": "writing database queries", "similarity": 0.85},
    ]


@pytest.mark.parametrize("ranking", [
    [("SQL", 0.4), ("PostgreSQL", 0.1)],
    [("SQL", 0.9), ("PostgreSQL", 0.89)],
    [("PostgreSQL", 0.95), ("SQL", 0.7)],
])
def test_low_ambiguous_or_unrequested_skill_is_not_matched(monkeypatch, ranking) -> None:
    monkeypatch.setattr(matcher, "rank_skills", lambda phrases: [ranking])
    result, _ = matcher.analyze_semantic_match(["SQL"], ["database work"])
    assert result["match_score"] == 0


@pytest.mark.parametrize("skills", [["Java"], ["no Python experience"], [], ["not skilled in SQL"]])
def test_known_alternatives_and_denials_do_not_trigger_inference(monkeypatch, skills) -> None:
    def unexpected_inference(phrases):
        raise AssertionError("Inference was not needed")
    monkeypatch.setattr(matcher, "rank_skills", unexpected_inference)
    result, details = matcher.analyze_semantic_match(["Python"], skills)
    assert result["match_score"] == 0
    assert details["semantic_matches"] == []


def test_semantic_evidence_is_saved_and_owner_scoped(authenticated_client, monkeypatch) -> None:
    monkeypatch.setattr(matcher, "rank_skills", lambda phrases: [
        [("SQL", 0.85), ("PostgreSQL", 0.5)],
    ])
    client = authenticated_client
    response = client.post("/api/analyze", json={
        "job_description": "SQL", "user_skills": ["writing database queries"],
        "matching_method": "semantic",
    })
    assert response.status_code == 200
    assert response.json()["match_score"] == 100
    record_id = client.get("/api/analyses").json()["items"][0]["id"]
    detail = client.get(f"/api/analyses/{record_id}").json()
    assert detail["matching_details"] == response.json()["matching_details"]
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={
        "email": "another@example.com", "password": "Another-password-27",
    })
    assert client.get(f"/api/analyses/{record_id}").status_code == 404


def test_unavailable_model_does_not_silently_save_an_exact_result(authenticated_client, monkeypatch) -> None:
    def unavailable(phrases):
        raise matcher.ModelUnavailableError("missing model")
    monkeypatch.setattr(matcher, "rank_skills", unavailable)
    response = authenticated_client.post("/api/analyze", json={
        "job_description": "SQL", "user_skills": ["writing queries"],
        "matching_method": "semantic",
    })
    assert response.status_code == 503
    assert authenticated_client.get("/api/analyses").json()["items"] == []


def test_unknown_matching_method_is_rejected(authenticated_client: TestClient) -> None:
    response = authenticated_client.post("/api/analyze", json={
        "job_description": "SQL", "user_skills": [], "matching_method": "unknown",
    })
    assert response.status_code == 422


def test_missing_model_files_fail_without_downloading(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(matcher, "get_settings", lambda: SimpleNamespace(semantic_model_path=tmp_path))
    matcher._load_model.cache_clear()
    with pytest.raises(matcher.ModelUnavailableError, match="not been installed"):
        matcher.rank_skills(["database queries"])


@pytest.mark.skipif(os.getenv("RUN_MODEL_TESTS") != "1", reason="Download the model and set RUN_MODEL_TESTS=1")
def test_real_local_model_matches_paraphrases_and_is_repeatable(monkeypatch) -> None:
    import socket

    def reject_network(*args, **kwargs):
        raise AssertionError("Model inference must run offline")
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    matcher._load_model.cache_clear()
    args = (["SQL", "CSS", "Python"], [
        "writing relational database queries", "styling web pages", "Python",
    ])
    first = matcher.analyze_semantic_match(*args)
    second = matcher.analyze_semantic_match(*args)
    assert first == second
    result, details = first
    assert result["match_score"] == 100
    assert details["exact_match_score"] == 33
    assert [item["skill"] for item in details["semantic_matches"]] == ["SQL", "CSS"]
