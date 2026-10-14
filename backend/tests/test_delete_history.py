import pytest


def test_delete_requires_account(client):
    assert client.delete("/api/analyses/1").status_code == 401


def test_owner_can_delete_saved_analysis(authenticated_client):
    client = authenticated_client
    client.post("/api/analyze", json={"job_description": "Python", "user_skills": []})
    item = client.get("/api/analyses").json()["items"][0]
    response = client.delete(f"/api/analyses/{item['id']}")
    assert response.status_code == 204 and response.content == b""
    assert client.get("/api/analyses").json()["total"] == 0
    assert client.get(f"/api/analyses/{item['id']}").status_code == 404


def test_foreign_analysis_cannot_be_deleted(authenticated_client):
    client = authenticated_client
    client.post("/api/analyze", json={"job_description": "Python", "user_skills": []})
    item = client.get("/api/analyses").json()["items"][0]
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"email": "other@example.com", "password": "Another-password-123"})
    assert client.delete(f"/api/analyses/{item['id']}").status_code == 404


@pytest.mark.parametrize("identifier", [0, -1, 2_147_483_648, 999999999999999999999])
def test_invalid_delete_ids_are_not_found(authenticated_client, identifier):
    assert authenticated_client.delete(f"/api/analyses/{identifier}").status_code == 404
