import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("authenticated_client")


def create_analysis(client: TestClient, description: str) -> dict[str, object]:
    response = client.post(
        "/api/analyze",
        json={"job_description": description, "user_skills": ["Python"]},
    )
    assert response.status_code == 200
    return response.json()


def test_history_is_empty_before_any_analyses(client: TestClient) -> None:
    response = client.get("/api/analyses")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 1,
        "page_size": 10,
        "total": 0,
        "total_pages": 0,
    }


def test_history_is_paginated_and_newest_first(client: TestClient) -> None:
    create_analysis(client, "First role needs SQL.")
    create_analysis(client, "Second role needs React.")
    create_analysis(client, "Third role needs Python.")

    first_page = client.get("/api/analyses?page=1&page_size=2")
    second_page = client.get("/api/analyses?page=2&page_size=2")

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert first_page.json()["total_pages"] == 2
    assert [item["job_description_preview"] for item in first_page.json()["items"]] == [
        "Third role needs Python.",
        "Second role needs React.",
    ]
    assert [item["job_description_preview"] for item in second_page.json()["items"]] == [
        "First role needs SQL."
    ]


def test_history_returns_compact_description_preview(client: TestClient) -> None:
    description = "Python " + "backend development " * 20
    create_analysis(client, description)

    response = client.get("/api/analyses")
    preview = response.json()["items"][0]["job_description_preview"]

    assert len(preview) == 180
    assert preview.endswith("...")
    assert "  " not in preview


def test_history_detail_returns_the_complete_record(client: TestClient) -> None:
    description = "Python, SQL and Git are required."
    create_analysis(client, description)
    analysis_id = client.get("/api/analyses").json()["items"][0]["id"]

    response = client.get(f"/api/analyses/{analysis_id}")

    assert response.status_code == 200
    assert response.json()["job_description"] == description
    assert response.json()["user_skills"] == ["Python"]
    assert response.json()["extracted_skills"] == ["Python", "SQL", "Git"]
    assert response.json()["matched_skills"] == ["Python"]
    assert response.json()["missing_skills"] == ["SQL", "Git"]
    assert response.json()["match_score"] == 33
    assert response.json()["created_at"]


def test_history_detail_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/analyses/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis not found"}


def test_history_rejects_invalid_pagination(client: TestClient) -> None:
    assert client.get("/api/analyses?page=0").status_code == 422
    assert client.get("/api/analyses?page_size=51").status_code == 422
    assert client.get(f"/api/analyses?page={10 ** 30}").status_code == 422


@pytest.mark.parametrize("analysis_id", [-1, 0, 10 ** 30])
def test_out_of_range_analysis_id_is_not_found(client: TestClient, analysis_id: int) -> None:
    assert client.get(f"/api/analyses/{analysis_id}").status_code == 404


def test_history_beyond_last_page_is_empty(client: TestClient) -> None:
    create_analysis(client, "Python")
    response = client.get("/api/analyses?page=2147483647&page_size=50")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 1
