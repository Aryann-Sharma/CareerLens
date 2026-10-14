import os

import pytest

from backend.app.api.routes import analysis, resume
from backend.app.services.trained_extractor import suggested_skills, usable_skill_spans
from backend.tests.pdf_fixtures import make_pdf


TEXT = "be a team worker, and be diligent"
SPANS = [
    {"text": "a", "label": "skill", "start": 3, "end": 4},
    {"text": "team worker", "label": "skill", "start": 5, "end": 16},
    {"text": "diligent", "label": "skill", "start": 25, "end": 33},
]
PREDICTION = {"model": "test", "revision": "test", "experimental": True, "spans": SPANS}


@pytest.mark.parametrize("fragment", ["a", "A", "an", "the", "and", "be", "with", "and be", "a,", "...", "—", "123", " "])
def test_obvious_fragments_do_not_become_skills(fragment):
    assert suggested_skills(fragment, [{"text": fragment}]) == []


@pytest.mark.parametrize("skill", ["C", "R", "C++", "C#", "Go", "IT", "3D modelling", "team worker", "diligent", "working in a team", "attention to detail", "mise en place"])
def test_filter_preserves_real_short_skills_and_function_words_in_phrases(skill):
    span = {"text": skill, "start": 0, "end": len(skill), "label": "skill"}
    assert usable_skill_spans([span]) == [span]
    assert suggested_skills(skill, [span]) == [skill]


@pytest.mark.parametrize("matching", ["exact", "semantic"])
def test_fragments_are_removed_before_scoring_and_saving(authenticated_client, monkeypatch, matching):
    monkeypatch.setattr(analysis, "extract", lambda *args: PREDICTION)
    response = authenticated_client.post("/api/analyze", json={
        "job_description": TEXT, "extraction_method": "trained", "matching_method": matching,
        "user_skills": ["team worker"],
    })
    assert response.status_code == 200
    result = response.json()
    assert result["extracted_skills"] == ["team worker", "diligent"]
    assert result["missing_skills"] == ["diligent"]
    assert result["match_score"] == 50
    assert result["extraction_details"]["spans"] == SPANS[1:]
    saved = authenticated_client.get(response.headers["Location"]).json()
    assert saved["extracted_skills"] == result["extracted_skills"]
    assert saved["extraction_details"] == result["extraction_details"]


def test_all_fragments_give_empty_result_without_affecting_catalog(client, monkeypatch):
    monkeypatch.setattr(analysis, "extract", lambda *args: {**PREDICTION, "spans": SPANS[:1]})
    for text, expected in [("a", []), ("Python", ["Python"])]:
        result = client.post("/api/preview", json={"job_description": text, "extraction_method": "trained", "user_skills": []}).json()
        assert result["extracted_skills"] == expected
        assert result["match_score"] == 0
        assert result["extraction_details"]["spans"] == []


def test_pdf_import_and_saved_resume_reuse_share_filter(authenticated_client, monkeypatch):
    monkeypatch.setattr(resume, "extract", lambda *args: PREDICTION)
    client = authenticated_client
    pdf = make_pdf(TEXT)
    headers = {"Content-Type": "application/pdf"}
    uploaded = client.post("/api/resume", content=pdf, headers=headers)
    assert uploaded.status_code == 200
    assert uploaded.json()["skills"] == ["team worker", "diligent"]
    assert uploaded.json()["extraction"]["spans"] == SPANS[1:]
    assert client.put("/api/resume/saved", content=pdf, headers=headers).status_code == 200
    assert client.post("/api/resume/saved/skills").json() == uploaded.json()


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
def test_real_model_screenshot_regression(client):
    result = client.post("/api/preview", json={"job_description": TEXT, "extraction_method": "trained",
                                               "user_skills": ["team worker"]})
    assert result.status_code == 200
    assert result.json()["extracted_skills"] == ["team worker", "diligent"]
    assert result.json()["missing_skills"] == ["diligent"]
    assert result.json()["match_score"] == 50
