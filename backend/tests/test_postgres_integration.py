import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect, select
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.db.session import SessionLocal, engine
from backend.app.main import app
from backend.app.models.analysis import AnalysisRecord
from backend.app.models.user import User


@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Set RUN_POSTGRES_TESTS=1 and DATABASE_URL to a migrated PostgreSQL test database",
)
def test_application_flow_uses_postgresql() -> None:
    assert engine.dialect.name == "postgresql", "Use a disposable PostgreSQL database"
    description = "PostgreSQL integration check using Python and SQL."
    email = f"integration-{uuid4().hex}@example.com"
    second_email = f"integration-{uuid4().hex}@example.com"
    client = TestClient(app)

    try:
        registration = client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "Integration-password-27",
            },
        )
        assert registration.status_code == 201
        assert registration.json()["email"] == email

        current_user = client.get("/api/auth/me")
        assert current_user.status_code == 200
        assert current_user.json()["id"] == registration.json()["id"]
        assert current_user.json()["created_at"].endswith("Z")
        assert client.get("/health/ready").status_code == 200

        response = client.post(
            "/api/analyze",
            json={
                "job_description": description,
                "user_skills": ["Python", "PostgreSQL"],
            },
        )

        assert response.status_code == 200
        assert response.json()["match_score"] == 67

        history = client.get("/api/analyses")
        assert history.status_code == 200
        history_item = next(
            item
            for item in history.json()["items"]
            if item["job_description_preview"] == description
        )
        analysis_id = history_item["id"]
        assert history_item["created_at"].endswith("Z")
        detail = client.get(f"/api/analyses/{analysis_id}")
        assert detail.status_code == 200
        assert detail.json()["job_description"] == description

        with SessionLocal() as session:
            saved_analysis = session.scalar(
                select(AnalysisRecord).where(AnalysisRecord.id == analysis_id)
            )
            assert saved_analysis is not None
            assert saved_analysis.user_id == registration.json()["id"]

        assert client.post("/api/auth/logout").status_code == 204
        second_registration = client.post(
            "/api/auth/register",
            json={
                "email": second_email,
                "password": "Integration-password-27",
            },
        )
        assert second_registration.status_code == 201
        assert client.get("/api/analyses").json()["items"] == []
        assert client.get(f"/api/analyses/{analysis_id}").status_code == 404

        assert engine.dialect.name == "postgresql"
        inspector = inspect(engine)
        analysis_columns = {
            column["name"]: column
            for column in inspector.get_columns("analyses")
        }
        assert isinstance(analysis_columns["user_skills"]["type"], JSONB)
        assert analysis_columns["user_id"]["nullable"] is True
        assert any(
            foreign_key["name"] == "fk_analyses_user_id_users"
            for foreign_key in inspector.get_foreign_keys("analyses")
        )
        assert any(
            index["name"] == "ix_analyses_user_id_created_at"
            for index in inspector.get_indexes("analyses")
        )
        assert {column["name"] for column in inspector.get_columns("users")} == {
            "id",
            "email",
            "password_hash",
            "created_at",
        }
        assert any(
            constraint["name"] == "uq_users_email"
            for constraint in inspector.get_unique_constraints("users")
        )
    finally:
        with SessionLocal() as session:
            session.execute(
                delete(AnalysisRecord).where(
                    AnalysisRecord.job_description == description
                )
            )
            session.execute(
                delete(User).where(User.email.in_([email, second_email]))
            )
            session.commit()
