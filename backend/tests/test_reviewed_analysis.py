from backend.app.api.routes import analysis
from backend.app.services.trained_extractor import ExtractorUnavailableError


def test_trained_spans_drive_scoring_and_are_saved(authenticated_client, monkeypatch):
    text = "Python and stakeholder communication"
    spans = [{"text": "stakeholder communication", "label": "skill", "start": 11, "end": len(text)}]
    monkeypatch.setattr(analysis, "extract", lambda *args: {"model": "test", "revision": "abc", "spans": spans})
    result = authenticated_client.post("/api/analyze", json={"job_description": text,
        "user_skills": ["stakeholder communication"], "extraction_method": "trained"})
    assert result.status_code == 200
    assert result.json()["match_score"] == 50
    assert result.json()["extracted_skills"] == ["Python", "stakeholder communication"]
    item = authenticated_client.get("/api/analyses").json()["items"][0]
    detail = authenticated_client.get(f"/api/analyses/{item['id']}").json()
    assert detail["extraction_details"] == result.json()["extraction_details"]


def test_reviewed_skills_override_predictions_without_model(client, monkeypatch):
    monkeypatch.setattr(analysis, "extract", lambda *args: (_ for _ in ()).throw(AssertionError("Must not run")))
    result = client.post("/api/preview", json={"job_description": "Python and SQL",
        "user_skills": ["Python"], "extraction_method": "trained", "reviewed_job_skills": [" python ", "Python"]})
    assert result.status_code == 200
    assert result.json()["extracted_skills"] == ["Python"]
    assert result.json()["match_score"] == 100
    assert result.json()["extraction_details"]["method"] == "reviewed"


def test_review_can_remove_all_skills(client):
    result = client.post("/api/preview", json={"job_description": "Python", "user_skills": ["Python"], "reviewed_job_skills": []})
    assert result.json()["extracted_skills"] == []
    assert result.json()["match_score"] == 0


def test_review_validation(client):
    for skills in (["x" * 101], [str(i) for i in range(201)]):
        assert client.post("/api/preview", json={"job_description": "Python", "user_skills": [], "reviewed_job_skills": skills}).status_code == 422


def test_trained_failure_is_explicit(client, monkeypatch):
    def unavailable(*args):
        raise ExtractorUnavailableError("Missing")
    monkeypatch.setattr(analysis, "extract", unavailable)
    assert client.post("/api/preview", json={"job_description": "Python", "user_skills": [], "extraction_method": "trained"}).status_code == 503
