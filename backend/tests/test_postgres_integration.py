import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.db.session import SessionLocal, engine
from backend.app.main import app
from backend.app.models.analysis import AnalysisRecord
from backend.app.models.user import User


@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="PostgreSQL integration test is only enabled in CI",
)
def test_application_flow_uses_postgresql() -> None:
    description = "PostgreSQL integration check using Python and SQL."
    email = f"integration-{uuid4().hex}@example.com"
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
        assert any(
            item["job_description_preview"] == description
            for item in history.json()["items"]
        )

        assert engine.dialect.name == "postgresql"
        inspector = inspect(engine)
        analysis_columns = {
            column["name"]: column
            for column in inspector.get_columns("analyses")
        }
        assert isinstance(analysis_columns["user_skills"]["type"], JSONB)
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
            session.execute(delete(User).where(User.email == email))
            session.commit()
