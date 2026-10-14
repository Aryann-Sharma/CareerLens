import os

import pytest

from backend.app.services.span_context import merge_context_spans, review_fragments
from backend.tests.pdf_fixtures import make_pdf


def span(text, value, label="skill"):
    start = text.index(value)
    return {"text": value, "start": start, "end": start + len(value), "label": label}


def test_list_candidates_keep_offsets_and_stop_at_other_sections():
    text = "Skills to build\na\nteam worker\n- diligent\nBenefits:\noffice building\n"
    regions = review_fragments(text, [])
    assert [text[r["start"]:r["end"]] for r in regions] == ["a", "team worker", "diligent"]
    assert all(r["allow_new"] for r in regions)


@pytest.mark.parametrize("heading", ["Skills", "SKILLS TO BUILD", "Required skills", "2. Qualifications", "## Technical skills"])
def test_skill_heading_variations(heading):
    text = f"{heading}:\n1. team worker\n2. diligent"
    assert [text[r["start"]:r["end"]] for r in review_fragments(text, [])] == ["team worker", "diligent"]


def test_inline_skill_heading_and_unicode_offsets():
    text = "🧭\nRequired skills: team worker"
    region = review_fragments(text, [])[0]
    assert text[region["start"]:region["end"]] == "team worker"
    assert region["allow_new"]


def test_context_pass_is_bounded_and_skips_sentences_or_long_lines():
    assert len(review_fragments("Skills:\n" + "team worker\n" * 300, [])) == 200
    assert review_fragments("Skills:\n" + "x" * 101, []) == []
    assert review_fragments("Skills:\nWe work in an office building.", []) == []
    assert review_fragments("office building", []) == []
    assert review_fragments("Skills:\ncommunication\n\noffice building", [])[-1]["end"] == len("Skills:\ncommunication")


@pytest.mark.parametrize("lead", [
    "We want", "We need", "We require", "We seek", "We are looking for", "We are seeking",
    "You must be", "You should be", "Candidates need to be", "An applicant",
])
def test_requirement_leads_retain_source_offsets(lead):
    text = f"🧭\n{lead} a diligent team worker, who is passionate."
    regions = review_fragments(text, [])
    if lead == "An applicant":
        assert regions == []  # No affirmative requirement verb.
    else:
        assert [text[r["start"]:r["end"]] for r in regions] == ["a diligent team worker"]
        assert regions[0]["allow_new"]


@pytest.mark.parametrize("text", [
    "We do not need a team worker.", "We need no prior experience.",
    "You must not be a team worker.", "We want someone without experience.",
    "We need someone who isn't a team worker.", "Our team worker mentors new starters.",
    "Benefits:\nWe want a new office building.",
])
def test_context_pass_does_not_add_candidates_in_negated_or_unrelated_text(text):
    assert review_fragments(text, []) == []


def test_requirement_clauses_keep_technology_punctuation_and_batch_limit():
    text = "We require Node.js; you must have Python."
    assert [text[r["start"]:r["end"]] for r in review_fragments(text, [])] == ["Node.js", "Python"]
    assert len(review_fragments("We want a team worker. " * 250, [])) == 200
    assert review_fragments("We want " + "long " * 17 + ".", []) == []


def test_only_extends_one_existing_phrase_outside_a_skill_list():
    text = "a diligent team worker"
    original = [span(text, "diligent"), span(text, "team")]
    regions = review_fragments(text, original)
    assert not regions[0]["allow_new"]
    extended = merge_context_spans(text, original, [span(text, "diligent"), span(text, "team worker")], regions)
    assert [s["text"] for s in extended] == ["diligent", "team worker"]
    assert original[1]["text"] == "team"
    assert merge_context_spans(text, original, [span(text, "a")], regions) == original
    assert merge_context_spans(text, original, [span(text, "diligent team worker")], regions) == original


@pytest.mark.parametrize("separator", [", ", " and ", " or ", "\n"])
def test_extension_cannot_swallow_another_item(separator):
    text = "team" + separator + "worker"
    original = [span(text, "team")]
    regions = [{"start": 0, "end": len(text), "allow_new": False}]
    assert merge_context_spans(text, original, [span(text, text)], regions) == original


def test_context_cannot_shrink_or_invent_spans():
    text = "Skills:\nteam worker"
    original = [span(text, "team worker")]
    regions = review_fragments(text, original)
    assert merge_context_spans(text, original, [span(text, "team")], regions) == original
    invented = {**span(text, "team worker"), "text": "team player"}
    assert merge_context_spans(text, [], [invented], regions) == []


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
@pytest.mark.parametrize("text,expected", [
    ("Skills to build\na\nteam worker\ndiligent", ["team worker", "diligent"]),
    ("a diligent team worker", ["diligent", "team worker"]),
    ("a diligent team player", ["diligent", "team player"]),
    ("team worker and diligent", ["team worker", "diligent"]),
    ("Skills:\n- communication\n- problem solving", ["communication", "problem solving"]),
    ("Required skills:\n1. team worker\n2. diligent", ["team worker", "diligent"]),
    ("Required skills:\n1.team worker\n2.diligent", ["team worker", "diligent"]),
    ("Skills:\nteam worker\nBenefits:\nPaid holidays", ["team worker"]),
    ("office building", []),
    ("team meetings", []),
    ("we want a diligent team worker, who is also very passionate and a hard-worker.",
     ["diligent", "team worker", "passionate", "hard-worker"]),
    ("We need a diligent team worker.", ["diligent", "team worker"]),
    ("We are looking for a reliable team player.", ["reliable", "team player"]),
    ("You must be a diligent team worker.", ["diligent", "team worker"]),
    ("Candidates should have attention to detail.", ["attention to detail"]),
    ("Applicants need to demonstrate problem solving.", ["problem solving"]),
    ("We are seeking a diligent team worker; you must have attention to detail.",
     ["diligent", "team worker", "attention to detail"]),
    ("WE WANT A DILIGENT TEAM WORKER.", ["DILIGENT", "TEAM WORKER"]),
    ("We need a new office building.", []),
    ("Our team worker mentors new starters.", []),
    ("We offer paid holidays and free lunches.", []),
])
def test_real_model_short_phrase_regressions(client, text, expected):
    result = client.post("/api/preview", json={"job_description": text, "extraction_method": "trained", "user_skills": []})
    assert result.status_code == 200
    body = result.json()
    assert body["extracted_skills"] == body["missing_skills"] == expected
    for found in body["extraction_details"]["spans"]:
        assert text[found["start"]:found["end"]] == found["text"]


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
def test_real_model_shared_pdf_and_history_workflows(authenticated_client):
    client = authenticated_client
    text = "Skills to build\na\nteam worker\ndiligent"
    expected = ["team worker", "diligent"]
    for matching in ("exact", "semantic"):
        result = client.post("/api/analyze", json={"job_description": text, "extraction_method": "trained", "matching_method": matching, "user_skills": ["team worker"]})
        assert result.status_code == 200
        assert result.json()["match_score"] == 50
        assert result.json()["missing_skills"] == ["diligent"]
        assert client.get(result.headers["Location"]).json()["extracted_skills"] == expected
    pdf = make_pdf(text)
    headers = {"Content-Type": "application/pdf"}
    assert client.post("/api/resume", content=pdf, headers=headers).json()["skills"] == expected
    assert client.put("/api/resume/saved", content=pdf, headers=headers).status_code == 200
    assert client.post("/api/resume/saved/skills").json()["skills"] == expected


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
def test_raw_extraction_catalog_and_manual_overrides_are_unchanged(client):
    text = "a diligent team worker"
    raw = client.post("/api/extract", json={"job_description": text}).json()
    assert [s["text"] for s in raw["spans"]] == ["diligent", "team"]
    assert client.post("/api/preview", json={"job_description": text, "extraction_method": "catalog", "user_skills": []}).json()["extracted_skills"] == []
    reviewed = client.post("/api/preview", json={"job_description": text, "extraction_method": "trained", "reviewed_job_skills": ["team"], "user_skills": []})
    assert reviewed.json()["extracted_skills"] == ["team"]
