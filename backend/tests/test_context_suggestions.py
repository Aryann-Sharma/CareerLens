import json
import os
from pathlib import Path

import pytest

from backend.app.api.routes import analysis
from backend.app.services.context_suggestions import evidence_units, suggest_from_context
from backend.app.services.semantic_matcher import ModelUnavailableError
from backend.app.services.skill_spelling import spelling_checks, correct_known_typos
from backend.app.services.workplace_phrases import PHRASES, preserve_phrases
from backend.app.services.trained_extractor import usable_skill_spans


@pytest.mark.parametrize("typo,expected", [
    ("hardworker", "hard worker"), ("hardwroker", "hard worker"),
    ("teamworker", "team worker"), ("team wokrer", "team worker"),
    ("problem solvig", "problem solving"), ("critical thinkng", "critical thinking"),
    ("timemanagement", "time management"), ("active listenng", "active listening"),
    ("selfmotivated", "self motivated"), ("detailoriented", "detail oriented"),
])
def test_compound_spelling_with_offsets_and_case(typo, expected):
    text = f"🧭 We want someone {typo.upper()}."
    checks = spelling_checks(text)
    assert any(expected in c["candidates"] for c in checks)
    assert all(not c["applied"] and text[c["start"]:c["end"]] == c["original"] for c in checks)
    assert correct_known_typos(text) == text


def test_valid_compounds_case_hyphens_and_plural_are_not_typos():
    for phrase in (*PHRASES, "hardworking", "hard worker", "team workers"):
        for variant in (phrase, phrase.upper(), phrase.replace(" ", "-")):
            assert spelling_checks(variant) == []


def test_both_reported_spelling_checks_survive():
    checks = spelling_checks("pasionate about work, and a hardworker. also need to be diligent with tasks and punctual.")
    assert [c["candidates"] for c in checks] == [["passionate"], ["hard worker"]]


def test_unspecified_actions_do_not_become_skill_names():
    spans = [{"text": value} for value in ("delete it", "rewrite it", "fix them", "write clean code", "problem solving")]
    assert usable_skill_spans(spans) == spans[3:]


def test_compounds_join_only_contained_fragments_and_preserve_longer_spans():
    text = "a hard worker"
    spans = [{"text":"hard", "start":2,"end":6,"label":"skill"}, {"text":"worker","start":7,"end":13,"label":"skill"}]
    assert preserve_phrases(text, spans) == [{"text":"hard worker","start":2,"end":13,"label":"skill"}]
    longer = [{"text":text, "start":0,"end":len(text),"label":"skill"}]
    assert preserve_phrases(text, longer) == longer
    assert preserve_phrases("We do not need a hard worker.", []) == []
    assert preserve_phrases("Benefits:\nFree customer service training", []) == []


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
@pytest.mark.parametrize("text", [
    "pasionate about work, and a hard worker. also need to be diligent with tasks and punctual.",
    "Hard worker", "We need a hard worker.", "Dedicated, a hard worker and dependable.",
    "A HARD WORKER with excellent attention to detail.",
])
def test_real_model_recovers_complete_compound(client, text):
    body = client.post("/api/preview", json={"job_description":text,"user_skills":[],"extraction_method":"trained"}).json()
    skills = [s.casefold() for s in body["extracted_skills"]]
    assert "hard worker" in skills
    assert "hard" not in skills and "worker" not in skills
    for span in body["extraction_details"]["spans"]:
        assert text[span["start"]:span["end"]] == span["text"]


def test_units_exclude_denials_benefits_and_bound_long_documents():
    assert evidence_units("We do not require programming, writing application code or testing software.") == []
    assert evidence_units("Benefits:\nWe offer classes on writing clear software documentation.") == []
    text = "🧭 Write code for our applications.\n" * 100 + "Resolve customer complaints patiently and help people use their purchases."
    units = evidence_units(text)
    assert len(units) == 48 and units[-1]["text"].startswith("Resolve customer")
    assert all(text[u["start"]:u["end"]] == u["text"] for u in units)


def test_interpretations_are_opt_in_review_only_and_saved(authenticated_client, monkeypatch):
    monkeypatch.setattr(analysis, "extract", lambda *args: {"model":"test","revision":"test","spans":[]})
    suggestion = {"skill":"Programming","evidence":"Write application code with care.","start":0,"end":33,"similarity":0.8}
    calls = []
    monkeypatch.setattr(analysis,"suggest_from_context",lambda *args: (calls.append(args) or [suggestion], "Review first"))
    request = {"job_description":suggestion["evidence"],"user_skills":["Programming"],"extraction_method":"trained"}
    assert authenticated_client.post("/api/preview",json=request).json()["match_score"] == 0
    assert calls == []
    response = authenticated_client.post("/api/analyze",json={**request,"interpret_duties":True})
    body = response.json()
    assert body["match_score"] == 0 and body["extracted_skills"] == []
    assert body["extraction_details"]["context_suggestions"] == [suggestion]
    assert authenticated_client.get(response.headers["Location"]).json()["extraction_details"]["context_suggestions"] == [suggestion]
    reviewed = authenticated_client.post("/api/preview",json={**request,"interpret_duties":True,"reviewed_job_skills":["Programming"]}).json()
    assert reviewed["match_score"] == 100 and len(calls) == 1


def test_missing_context_model_does_not_break_existing_analysis(client, monkeypatch):
    monkeypatch.setattr(analysis,"extract",lambda *args:{"model":"test","revision":"test","spans":[]})
    def unavailable(*args):
        raise ModelUnavailableError()
    monkeypatch.setattr(analysis,"suggest_from_context",unavailable)
    body = client.post("/api/preview",json={"job_description":"Python", "user_skills":["Python"], "extraction_method":"trained", "interpret_duties":True}).json()
    assert body["match_score"] == 100
    assert "unavailable" in body["extraction_details"]["context_notice"]


@pytest.mark.skipif(os.getenv("RUN_MODEL_TESTS") != "1", reason="Requires local sentence model")
@pytest.mark.parametrize("filename", ["context-cases", "context-holdout"])
def test_real_context_report_reproduces_and_evidence_is_original(filename):
    cases = json.loads(Path(f"evaluation/{filename}.json").read_text(encoding="utf-8"))["cases"]
    report_name = "context-results" if filename == "context-cases" else "context-holdout-results"
    recorded = json.loads(Path(f"evaluation/{report_name}.json").read_text(encoding="utf-8"))["results"]
    for case, record in zip(cases, recorded, strict=True):
        suggestions, _ = suggest_from_context(case["text"], [])
        assert sorted(s["skill"] for s in suggestions) == record["predicted"]
        assert all(case["text"][s["start"]:s["end"]] == s["evidence"] for s in suggestions)
        assert len(suggestions) <= 6


@pytest.mark.skipif(os.getenv("RUN_MODEL_TESTS") != "1", reason="Requires local sentence model")
def test_known_skills_case_are_not_suggested_again():
    assert suggest_from_context("Write clear application code to implement new features.", ["PROGRAMMING"])[0] == []
