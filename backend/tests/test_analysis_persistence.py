import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.analysis import AnalysisRecord
from backend.app.models.user import User
from backend.app.services.analysis_store import save_analysis

pytestmark = pytest.mark.usefixtures("authenticated_client")


def test_successful_analysis_is_saved(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post(
        "/api/analyze",
        json={
            "job_description": "We need Python, SQL and React.",
            "user_skills": ["Python", "SQL"],
        },
    )

    assert response.status_code == 200

    record = db_session.scalar(select(AnalysisRecord))
    assert record is not None
    assert record.user_id is not None
    assert record.job_description == "We need Python, SQL and React."
    assert record.user_skills == ["Python", "SQL"]
    assert record.extracted_skills == ["Python", "SQL", "React"]
    assert record.matched_skills == ["Python", "SQL"]
    assert record.missing_skills == ["React"]
    assert record.match_score == 67
    assert record.created_at is not None


def test_invalid_request_is_not_saved(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post(
        "/api/analyze",
        json={"job_description": "   ", "user_skills": ["Python"]},
    )

    assert response.status_code == 422
    assert db_session.scalar(select(AnalysisRecord)) is None


def test_each_analysis_creates_a_separate_record(
    client: TestClient,
    db_session: Session,
) -> None:
    for description in ["Python is required.", "SQL is required."]:
        response = client.post(
            "/api/analyze",
            json={"job_description": description, "user_skills": []},
        )
        assert response.status_code == 200

    records = db_session.scalars(
        select(AnalysisRecord).order_by(AnalysisRecord.id)
    ).all()
    assert [record.job_description for record in records] == [
        "Python is required.",
        "SQL is required.",
    ]


def test_failed_write_rolls_back_the_transaction(db_session: Session) -> None:
    user_id = db_session.scalar(select(User.id))
    assert user_id is not None

    with pytest.raises(IntegrityError):
        save_analysis(
            db_session,
            user_id=user_id,
            job_description="Python is required.",
            user_skills=["Python"],
            extracted_skills=["Python"],
            result={
                "matched_skills": ["Python"],
                "missing_skills": [],
                "match_score": 101,
            },
        )

    saved_count = db_session.scalar(
        select(func.count()).select_from(AnalysisRecord)
    )
    assert saved_count == 0


def test_unknown_owner_is_rejected(db_session: Session) -> None:
    record = AnalysisRecord(
        user_id=999,
        job_description="Python is required.",
        user_skills=["Python"],
        extracted_skills=["Python"],
        matched_skills=["Python"],
        missing_skills=[],
        match_score=100,
    )
    db_session.add(record)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
