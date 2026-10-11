import pytest
from sqlalchemy import func, select

from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.analysis import AnalysisRecord
from backend.app.services import semantic_matcher

REQUEST = {"job_description": "Python and SQL", "user_skills": ["Python"]}


def test_guest_preview_works_without_database_or_session(client):
    def no_database():
        raise AssertionError("Public preview should not need a database")
    app.dependency_overrides[get_db] = no_database
    response = client.post("/api/preview", json=REQUEST)
    assert response.status_code == 200
    assert response.json()["match_score"] == 50


def test_preview_never_saves_even_when_signed_in(authenticated_client, db_session):
    for _ in range(2):
        assert authenticated_client.post("/api/preview", json=REQUEST).status_code == 200
    assert db_session.scalar(select(func.count()).select_from(AnalysisRecord)) == 0


def test_guest_cannot_save_or_read_history(client):
    assert client.post("/api/analyze", json=REQUEST).status_code == 401
    assert client.get("/api/analyses").status_code == 401
    assert client.get("/api/analyses/1").status_code == 401


def test_preview_then_sign_in_and_save_recomputes_the_result(client):
    preview = client.post("/api/preview", json=REQUEST).json()
    assert client.post("/api/auth/register", json={
        "email": "guest-save@example.com", "password": "Guest-password-27",
    }).status_code == 201
    assert client.get("/api/analyses").json()["total"] == 0
    assert client.post("/api/analyze", json={**REQUEST, "match_score": 100}).status_code == 422
    saved = client.post("/api/analyze", json=REQUEST)
    assert saved.status_code == 200 and saved.json() == preview
    assert client.get("/api/analyses").json()["total"] == 1


def test_guest_semantic_matching_has_the_same_evidence(client, monkeypatch):
    monkeypatch.setattr(semantic_matcher, "rank_skills", lambda phrases: [[("SQL", .9), ("Python", .2)]])
    response = client.post("/api/preview", json={
        "job_description": "SQL", "user_skills": ["writing database queries"],
        "matching_method": "semantic",
    })
    assert response.status_code == 200
    assert response.json()["matching_details"]["semantic_matches"][0]["skill"] == "SQL"


@pytest.mark.parametrize("payload", [
    {**REQUEST, "job_description": " "}, {**REQUEST, "job_description": "x" * 50001},
    {**REQUEST, "matching_method": "invalid"}, {**REQUEST, "user_skills": ["x" * 101]},
])
def test_guest_input_validation(client, payload):
    assert client.post("/api/preview", json=payload).status_code == 422
