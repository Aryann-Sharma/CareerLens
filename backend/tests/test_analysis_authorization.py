from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.analysis import AnalysisRecord


def register(client: TestClient, email: str) -> int:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Test-password-27"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_analysis(client: TestClient, description: str) -> int:
    response = client.post(
        "/api/analyze",
        json={
            "job_description": description,
            "user_skills": ["Python"],
        },
    )
    assert response.status_code == 200

    history = client.get("/api/analyses")
    assert history.status_code == 200
    return history.json()["items"][0]["id"]


def test_analysis_routes_require_authentication(client: TestClient) -> None:
    analysis = client.post(
        "/api/analyze",
        json={
            "job_description": "Python is required.",
            "user_skills": ["Python"],
        },
    )

    assert analysis.status_code == 401
    assert client.get("/api/analyses").status_code == 401
    assert client.get("/api/analyses/1").status_code == 401


def test_users_only_see_their_own_analyses(
    client: TestClient,
    db_session: Session,
) -> None:
    first_user_id = register(client, "first@example.com")
    first_analysis_id = create_analysis(client, "Python is required.")

    assert client.post("/api/auth/logout").status_code == 204
    second_user_id = register(client, "second@example.com")

    second_user_history = client.get("/api/analyses")
    first_user_detail = client.get(f"/api/analyses/{first_analysis_id}")

    assert second_user_history.status_code == 200
    assert second_user_history.json()["items"] == []
    assert first_user_detail.status_code == 404
    assert first_user_detail.json() == {"detail": "Analysis not found"}

    second_analysis_id = create_analysis(client, "Python and SQL are required.")
    assert second_analysis_id != first_analysis_id

    records = db_session.scalars(
        select(AnalysisRecord).order_by(AnalysisRecord.id)
    ).all()
    assert [record.user_id for record in records] == [
        first_user_id,
        second_user_id,
    ]


def test_client_cannot_choose_analysis_owner(client: TestClient) -> None:
    register(client, "student@example.com")

    response = client.post(
        "/api/analyze",
        json={
            "job_description": "Python is required.",
            "user_skills": ["Python"],
            "user_id": 999,
        },
    )

    assert response.status_code == 422


def test_legacy_unowned_analysis_is_not_exposed(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client, "student@example.com")
    legacy_record = AnalysisRecord(
        user_id=None,
        job_description="Legacy Python role.",
        user_skills=["Python"],
        extracted_skills=["Python"],
        matched_skills=["Python"],
        missing_skills=[],
        match_score=100,
    )
    db_session.add(legacy_record)
    db_session.commit()
    db_session.refresh(legacy_record)

    history = client.get("/api/analyses")
    detail = client.get(f"/api/analyses/{legacy_record.id}")

    assert history.status_code == 200
    assert history.json()["items"] == []
    assert detail.status_code == 404
