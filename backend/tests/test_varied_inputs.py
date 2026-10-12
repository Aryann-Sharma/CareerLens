import os

import pytest

from backend.tests.varied_input_fixtures import DOCUMENT_CASES, FORMATS, REVIEW_CORRECTIONS, document_bytes, varied_descriptions


@pytest.mark.parametrize("method", ["catalog", "trained"])
@pytest.mark.parametrize("text,expected,profile", varied_descriptions(), ids=[f"sample-{i:02d}" for i in range(32)])
def test_seeded_descriptions_preserve_named_skills_and_consistent_scores(client, method, text, expected, profile):
    if method == "trained" and os.getenv("RUN_CONTEXTUAL_TESTS") != "1":
        pytest.skip("Requires contextual weights")
    response = client.post("/api/preview", json={"job_description": text, "extraction_method": method,
                                                "matching_method": "exact", "user_skills": profile})
    assert response.status_code == 200
    result = response.json()
    found = result["extracted_skills"]
    assert set(expected) <= set(found)
    assert len(found) == len({skill.casefold() for skill in found})
    assert set(result["matched_skills"]) == set(profile)
    assert set(result["missing_skills"]) == set(found) - set(profile)
    assert result["match_score"] == round(100 * len(profile) / len(found))
    for item in result.get("extraction_details", {}).get("spans", []):
        assert text[item["start"]:item["end"]] == item["text"]


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
@pytest.mark.parametrize("format,media", FORMATS)
@pytest.mark.parametrize("name,text,expected", DOCUMENT_CASES, ids=[case[0] for case in DOCUMENT_CASES])
def test_real_document_to_trained_analysis(client, name, text, expected, format, media):
    route = "/api/job-pdf" if format == "PDF" else "/api/job-image"
    response = client.post(route, content=document_bytes(text, format), headers={"Content-Type": media})
    assert response.status_code == 200, response.text
    imported = response.json()
    if name == "full-posting":
        assert imported["selection_applied"]
        assert "Java" in imported["full_text"] and "Java" not in imported["text"]
    reviewed = REVIEW_CORRECTIONS.get((name, format), imported["text"])
    analysis = client.post("/api/preview", json={"job_description": reviewed, "extraction_method": "trained",
                                                "matching_method": "exact", "user_skills": expected})
    assert analysis.status_code == 200
    result = analysis.json()
    assert set(result["extracted_skills"]) == set(expected), imported["text"]
    assert set(result["matched_skills"]) == set(expected)
    assert result["missing_skills"] == [] and result["match_score"] == 100
