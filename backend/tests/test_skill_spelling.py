import os

import pytest

from backend.app.api.routes import analysis, resume
from backend.app.services.skill_spelling import COMMON_TYPOS, correct_known_typos, one_edit_apart, spelling_checks
from backend.app.services.trained_extractor import suggested_skills
from backend.tests.pdf_fixtures import make_pdf
from backend.app.services.skill_extractor import SKILL_ALIASES
from backend.app.services.skill_spelling import candidates


@pytest.mark.parametrize("skill,aliases", list(SKILL_ALIASES.items()))
def test_casing_alone_never_triggers_spelling_checks(skill, aliases):
    for spelling in (skill, *aliases):
        for variant in (spelling.lower(), spelling.upper(), spelling.swapcase()):
            assert spelling_checks(variant) == []
            assert correct_known_typos(variant) == variant
            if variant.isalpha():
                assert candidates(variant) == ()


@pytest.mark.parametrize("method", ["catalog", "trained"])
def test_mixed_case_job_skills_match_without_spelling_notes(client, monkeypatch, method):
    monkeypatch.setattr(analysis, "extract", lambda *args: {"model": "test", "revision": "test", "spans": []})
    result = client.post("/api/preview", json={"job_description": "pYtHoN JAVASCRIPT fast api NODE.JS",
        "user_skills": ["Python", "JavaScript", "FastAPI", "Node.js"], "extraction_method": method}).json()
    assert result["match_score"] == 100
    assert not (result.get("extraction_details") or {}).get("spelling")


def test_valid_multiword_alias_does_not_hide_a_later_uncertain_spelling():
    text = "POSTGRE SQL and postgre"
    checks = spelling_checks(text)
    assert len(checks) == 1
    assert checks[0]["start"] == text.rindex("postgre")


@pytest.mark.parametrize("typo,skill", list(COMMON_TYPOS.items()))
def test_documented_typos_are_corrected_with_original_offsets(typo, skill):
    text = f"🧭 Experience with {typo.upper()} and SQL."
    check = spelling_checks(text)[0]
    assert text[check["start"]:check["end"]] == typo.upper()
    assert check["applied"] is True
    assert check["candidates"] == [skill]
    assert correct_known_typos(text) == f"🧭 Experience with {skill} and SQL."


@pytest.mark.parametrize("left,right,expected", [
    ("python", "pyhton", True), ("python", "pythn", True), ("python", "pythonn", True),
    ("python", "pythom", True), ("python", "python", False), ("java", "javascript", False),
    ("python", "pytohnn", False), ("react", "reacts", True),
])
def test_spelling_distance(left, right, expected):
    assert one_edit_apart(left, right) is expected


def test_uncertain_spelling_is_suggested_without_rewriting_text():
    text = "Experience with Pythom and Reactt; update the docket."
    checks = spelling_checks(text)
    assert [check["candidates"] for check in checks] == [["Python"], ["React"], ["Docker"]]
    assert not any(check["applied"] for check in checks)
    assert correct_known_typos(text) == text


def test_known_skills_short_names_versions_and_compounds_are_not_guessed():
    text = "Java JavaScript TypeScript SQL CSS HTML Git C C++ C# R Go IT Python3 React-native xPyhton PyhtonX"
    assert spelling_checks(text) == []
    assert correct_known_typos(text) == text


def test_soft_skill_spelling_is_left_for_manual_review():
    text = "comunication skills and team wokrer"
    assert correct_known_typos(text) == text
    assert spelling_checks(text) == []


def test_repeated_corrected_skills_do_not_inflate_score():
    text = "Pyhton Python PYHTON"
    spans = [{"text": "Pyhton"}, {"text": "Python"}]
    assert suggested_skills(text, spans) == ["Python"]
    assert len(spelling_checks(text)) == 1


@pytest.mark.parametrize("method", ["catalog", "trained"])
def test_corrected_job_skills_drive_scoring_and_preserve_history(authenticated_client, monkeypatch, method):
    text = "Pyhton and Javascrip"
    spans = [{"text": "Pyhton", "start": 0, "end": 6, "label": "knowledge"},
             {"text": "Javascrip", "start": 11, "end": 20, "label": "knowledge"}]
    monkeypatch.setattr(analysis, "extract", lambda *args: {"model": "test", "revision": "test", "spans": spans})
    result = authenticated_client.post("/api/analyze", json={"job_description": text, "user_skills": ["Python", "JavaScript"], "extraction_method": method})
    assert result.status_code == 200
    assert result.json()["match_score"] == 100
    assert result.json()["extracted_skills"] == ["Python", "JavaScript"]
    assert len(result.json()["extraction_details"]["spelling"]) == 2
    detail = authenticated_client.get(result.headers["Location"]).json()
    assert detail["job_description"] == text
    assert {key: value for key, value in detail["extraction_details"].items() if value is not None} == result.json()["extraction_details"]
    if method == "trained":
        assert detail["extraction_details"]["spans"] == spans


def test_uncertain_correction_does_not_change_score_until_reviewed(client):
    request = {"job_description": "Pythom SQL", "user_skills": ["Python"], "extraction_method": "catalog"}
    result = client.post("/api/preview", json=request).json()
    assert result["extracted_skills"] == ["SQL"]
    assert result["match_score"] == 0
    assert result["extraction_details"]["spelling"][0]["applied"] is False
    reviewed = client.post("/api/preview", json={**request, "reviewed_job_skills": ["Python", "SQL"]}).json()
    assert reviewed["match_score"] == 50
    # Explicit user corrections override automatic spelling, even for a known typo.
    reverted = client.post("/api/preview", json={**request, "reviewed_job_skills": ["Pyhton"]}).json()
    assert reverted["extracted_skills"] == ["Pyhton"]
    assert reverted["extraction_details"]["spelling"] == []


@pytest.mark.parametrize("method", ["catalog", "trained"])
def test_resume_import_and_reuse_explain_corrections(authenticated_client, monkeypatch, method):
    monkeypatch.setattr(resume, "extract", lambda *args: {"model": "test", "revision": "test", "experimental": True, "spans": []})
    client = authenticated_client
    pdf = make_pdf("Pyhton Pythom SQL")
    headers = {"Content-Type": "application/pdf"}
    imported = client.post(f"/api/resume?method={method}", content=pdf, headers=headers).json()
    assert imported["skills"] == ["Python", "SQL"]
    assert [check["applied"] for check in imported["spelling"]] == [True, False]
    assert client.put("/api/resume/saved", content=pdf, headers=headers).status_code == 200
    assert client.post(f"/api/resume/saved/skills?method={method}").json() == imported
    assert client.get("/api/resume/saved/file").content == pdf


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
def test_real_model_typos_match_correctly_spelled_profile(client):
    result = client.post("/api/preview", json={"job_description": "Experience with Pyhton and Javascrip.",
        "extraction_method": "trained", "matching_method": "semantic", "user_skills": ["Python", "JavaScript"]})
    assert result.status_code == 200
    assert result.json()["extracted_skills"] == ["Python", "JavaScript"]
    assert result.json()["match_score"] == 100
