import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.db.session import SessionLocal, engine
from backend.app.main import app
from backend.app.models.analysis import AnalysisRecord


@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="PostgreSQL integration test is only enabled in CI",
)
def test_analysis_flow_uses_postgresql() -> None:
    description = "PostgreSQL integration check using Python and SQL."
    client = TestClient(app)

    try:
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
        columns = {
            column["name"]: column
            for column in inspect(engine).get_columns("analyses")
        }
        assert isinstance(columns["user_skills"]["type"], JSONB)
    finally:
        with SessionLocal() as session:
            session.execute(
                delete(AnalysisRecord).where(
                    AnalysisRecord.job_description == description
                )
            )
            session.commit()
