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
from backend.app.services.passwords import hash_password, verify_password


@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="PostgreSQL integration test is only enabled in CI",
)
def test_application_flow_uses_postgresql() -> None:
    description = "PostgreSQL integration check using Python and SQL."
    email = f"integration-{uuid4().hex}@example.com"
    client = TestClient(app)

    try:
        with SessionLocal() as session:
            user = User(
                email=email,
                password_hash=hash_password("Integration-password-27"),
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            assert user.id is not None
            assert verify_password(
                "Integration-password-27",
                user.password_hash,
            )

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
