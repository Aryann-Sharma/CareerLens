from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from backend.app.models import SavedRoadmap, User
from backend.app.services.learning import GUIDES, build_plan


def payload(**changes):
    return {"client_id": str(uuid4()), "title": "Java practice", "completed": ["0:0"],
            "plan_revision": build_plan(["Java"], [], None)["revision"],
            "request": {"missing_skills": ["Java"], "user_skills": []}, **changes}


def create(client, **changes):
    response = client.post("/api/learning/saved", json=payload(**changes))
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/learning/saved", None), ("GET", "/api/learning/saved/1", None),
    ("POST", "/api/learning/saved", payload()),
    ("PUT", "/api/learning/saved/1", {"title": "Changed", "completed": [], "version": 1}),
    ("DELETE", "/api/learning/saved/1?version=1", None),
])
def test_private_routes_require_authentication(client, method, path, body):
    assert client.request(method, path, json=body).status_code == 401


def test_save_read_update_preserves_steps_and_never_changes_analysis(authenticated_client, db_session):
    client = authenticated_client
    saved = create(client)
    url = f"/api/learning/saved/{saved['id']}"
    assert saved["title"] == "Java practice" and saved["version"] == 1
    assert saved["completed_count"] == 1 and saved["total_count"] == 3
    assert saved["created_at"].endswith("+00:00") or saved["created_at"].endswith("Z")
    assert client.get(url).json() == saved
    changed = client.put(url, json={"title": "  Java library project  ", "completed": ["0:2", "0:0", "0:2"], "version": 1})
    assert changed.status_code == 200
    assert changed.json()["completed"] == ["0:0", "0:2"]
    assert changed.json()["title"] == "Java library project"
    assert changed.json()["version"] == 2 and changed.json()["plan"] == saved["plan"]
    assert client.get("/api/analyses").json()["total"] == 0
    assert db_session.scalar(select(SavedRoadmap)).title == "Java library project"
    for response in (changed, client.get(url), client.get("/api/learning/saved")):
        assert response.headers["cache-control"] == "no-store"


def test_retry_create_returns_same_record_without_overwriting_progress(authenticated_client):
    client = authenticated_client
    request = payload()
    first = client.post("/api/learning/saved", json=request).json()
    client.put(f"/api/learning/saved/{first['id']}", json={"title": "New name", "version": 1, "completed": []})
    retry = client.post("/api/learning/saved", json=request)
    assert retry.status_code == 200 and retry.json()["id"] == first["id"]
    assert retry.json()["title"] == "New name" and retry.json()["version"] == 2
    assert client.get("/api/learning/saved").json()["total"] == 1


def test_stale_update_and_delete_cannot_overwrite_newer_changes(authenticated_client):
    client = authenticated_client
    saved = create(client)
    url = f"/api/learning/saved/{saved['id']}"
    current = client.put(url, json={"title": "New name", "version": 1, "completed": ["0:1"]}).json()
    assert client.put(url, json={"title": "Old name", "version": 1, "completed": []}).status_code == 409
    assert client.delete(url + "?version=1").status_code == 409
    assert client.get(url).json() == current
    assert client.delete(url + "?version=2").status_code == 204
    assert client.get(url).status_code == 404
    assert client.get("/api/learning/saved").json()["total"] == 0


def test_saved_steps_are_snapshots_not_rebuilt_from_changed_guides(authenticated_client, monkeypatch):
    client = authenticated_client
    saved = create(client)
    monkeypatch.setitem(GUIDES, "Java", {**GUIDES["Java"], "milestones": ["A changed curriculum"]})
    response = client.put(f"/api/learning/saved/{saved['id']}", json={"title": "Keep original steps", "completed": ["0:2"], "version": 1})
    assert response.status_code == 200
    assert response.json()["plan"] == saved["plan"]


def test_old_draft_cannot_apply_progress_to_new_learning_steps(authenticated_client, monkeypatch):
    draft = payload()
    monkeypatch.setitem(GUIDES, "Java", {**GUIDES["Java"], "milestones": ["A changed curriculum"]})
    response = authenticated_client.post("/api/learning/saved", json=draft)
    assert response.status_code == 409
    assert authenticated_client.get("/api/learning/saved").json()["total"] == 0


def test_accounts_are_isolated_and_same_client_key_is_scoped_to_owner(authenticated_client):
    client = authenticated_client
    request = payload()
    first = client.post("/api/learning/saved", json=request).json()
    url = f"/api/learning/saved/{first['id']}"
    client.post("/api/auth/logout")
    assert client.post("/api/auth/register", json={"email": "other-roadmaps@example.com", "password": "Other-password-27"}).status_code == 201
    assert client.get("/api/learning/saved").json()["total"] == 0
    assert client.get(url).status_code == 404
    assert client.put(url, json={"title": "Foreign", "completed": [], "version": 1}).status_code == 404
    assert client.delete(url + "?version=1").status_code == 404
    second = client.post("/api/learning/saved", json=request)
    assert second.status_code == 201 and second.json()["id"] != first["id"]


def test_browser_account_guard_blocks_cookie_changes(authenticated_client):
    client = authenticated_client
    user_id = client.get("/api/auth/me").json()["id"]
    headers = {"X-Account-ID": str(user_id + 1)}
    assert client.get("/api/learning/saved", headers=headers).status_code == 409
    assert client.post("/api/learning/saved", json=payload(), headers=headers).status_code == 409
    assert client.get("/api/learning/saved").json()["total"] == 0


def test_delete_owner_cascades_to_plans(authenticated_client, db_session):
    create(authenticated_client)
    db_session.execute(delete(User))
    db_session.commit()
    assert db_session.scalar(select(SavedRoadmap)) is None


def test_pagination_returns_metadata_in_stable_order(authenticated_client):
    client = authenticated_client
    ids = [create(client, title=f"Plan {i}")["id"] for i in range(7)]
    first = client.get("/api/learning/saved?page_size=5").json()
    second = client.get("/api/learning/saved?page=2&page_size=5").json()
    assert [row["id"] for row in first["items"] + second["items"]] == ids[::-1]
    assert first["total"] == 7
    assert all("plan" not in item for item in first["items"])
    assert client.get("/api/learning/saved?page=0").status_code == 422
    assert client.get("/api/learning/saved?page_size=51").status_code == 422
    assert client.get("/api/learning/saved/9999999999999999999999").status_code == 422


@pytest.mark.parametrize("changes", [
    {"title": " "}, {"title": "x" * 101}, {"completed": ["0:3"]}, {"completed": ["1:0"]},
    {"completed": ["-1:0"]}, {"completed": ["0:0"] * 655}, {"client_id": "not-a-uuid"},
    {"request": {"missing_skills": [], "direction": "nurse"}}, {"plan": {"url": "https://example.com"}},
])
def test_invalid_create_does_not_store_a_record(authenticated_client, changes):
    assert authenticated_client.post("/api/learning/saved", json=payload(**changes)).status_code == 422
    assert authenticated_client.get("/api/learning/saved").json()["total"] == 0


def test_invalid_update_preserves_saved_copy(authenticated_client):
    client = authenticated_client
    saved = create(client)
    url = f"/api/learning/saved/{saved['id']}"
    for changes in ({"version": True}, {"completed": ["999:0"]}, {"title": ""}, {"plan": {}}):
        response = client.put(url, json={"title": "Changed", "version": 1, "completed": [], **changes})
        assert response.status_code == 422
        assert client.get(url).json() == saved
