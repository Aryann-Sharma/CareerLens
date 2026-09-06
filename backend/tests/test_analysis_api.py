import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.schemas.analysis import AnalysisRequest

client = TestClient(app)


def test_analyze_endpoint_returns_expected_breakdown() -> None:
    response = client.post(
        "/api/analyze",
        json={
            "job_description": "We need Python, SQL, React, Git and FastAPI.",
            "user_skills": ["Python", "Java", "SQL", "Git"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "extracted_skills": ["Python", "SQL", "React", "Git", "FastAPI"],
        "matched_skills": ["Python", "SQL", "Git"],
        "missing_skills": ["React", "FastAPI"],
        "match_score": 60,
    }


def test_analyze_endpoint_rejects_blank_description() -> None:
    response = client.post(
        "/api/analyze", json={"job_description": "   ", "user_skills": []}
    )

    assert response.status_code == 422


def test_analyze_endpoint_accepts_an_empty_skill_list() -> None:
    response = client.post(
        "/api/analyze",
        json={
            "job_description": "Python and SQL are required.",
            "user_skills": [],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "extracted_skills": ["Python", "SQL"],
        "matched_skills": [],
        "missing_skills": ["Python", "SQL"],
        "match_score": 0,
    }


def test_analyze_endpoint_handles_no_recognised_skills() -> None:
    response = client.post(
        "/api/analyze",
        json={
            "job_description": "Strong communication and teamwork are required.",
            "user_skills": ["Python"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "extracted_skills": [],
        "matched_skills": [],
        "missing_skills": [],
        "match_score": 0,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"user_skills": ["Python"]},
        {"job_description": "Python is required."},
        {"job_description": 42, "user_skills": ["Python"]},
        {"job_description": "Python is required.", "user_skills": "Python"},
    ],
)
def test_analyze_endpoint_rejects_missing_or_incorrect_fields(
    payload: dict[str, object],
) -> None:
    response = client.post("/api/analyze", json=payload)

    assert response.status_code == 422


def test_analyze_endpoint_rejects_unknown_fields() -> None:
    response = client.post(
        "/api/analyze",
        json={
            "job_description": "Python is required.",
            "user_skills": ["Python"],
            "unexpected": True,
        },
    )

    assert response.status_code == 422


def test_analyze_endpoint_accepts_maximum_description_length() -> None:
    description = "Python " + "a" * 49_993

    response = client.post(
        "/api/analyze",
        json={"job_description": description, "user_skills": ["Python"]},
    )

    assert response.status_code == 200
    assert response.json()["match_score"] == 100


def test_analyze_endpoint_rejects_description_over_limit() -> None:
    description = "a" * 50_001

    response = client.post(
        "/api/analyze",
        json={"job_description": description, "user_skills": []},
    )

    assert response.status_code == 422


def test_analyze_endpoint_rejects_more_than_200_user_skills() -> None:
    response = client.post(
        "/api/analyze",
        json={
            "job_description": "Python is required.",
            "user_skills": [f"skill-{number}" for number in range(201)],
        },
    )

    assert response.status_code == 422


def test_request_schema_cleans_user_skills() -> None:
    request = AnalysisRequest(
        job_description="  Python is required.  ",
        user_skills=[" Python ", "python", "", "  SQL  "],
    )

    assert request.job_description == "Python is required."
    assert request.user_skills == ["Python", "SQL"]


def test_request_schema_rejects_an_overly_long_skill() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(
            job_description="Python is required.",
            user_skills=["a" * 101],
        )


def test_health_endpoint_still_works() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_analyze_endpoint_only_accepts_post_requests() -> None:
    response = client.get("/api/analyze")

    assert response.status_code == 405


def test_analyze_endpoint_is_in_openapi_schema() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "post" in response.json()["paths"]["/api/analyze"]
