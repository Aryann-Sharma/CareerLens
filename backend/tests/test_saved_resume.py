import pytest
from sqlalchemy import delete, func, select

from backend.app.models import SavedResume, User
from backend.tests.pdf_fixtures import make_pdf


def upload(client, text="Python SQL", filename="resume.pdf"):
    return client.put("/api/resume/saved", params={"filename": filename}, content=make_pdf(text),
                      headers={"Content-Type": "application/pdf"})


@pytest.mark.parametrize("method,path", [
    ("get", "/api/resume/saved"), ("put", "/api/resume/saved"),
    ("delete", "/api/resume/saved"), ("get", "/api/resume/saved/file"),
    ("post", "/api/resume/saved/skills"),
], ids=["metadata", "save", "delete", "download", "reuse"])
def test_saved_resume_requires_login(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_save_reuse_download_replace_delete(authenticated_client, db_session):
    client = authenticated_client
    assert client.get("/api/resume/saved").status_code == 404
    saved = upload(client)
    assert saved.status_code == 200
    assert set(saved.json()) == {"filename", "pages", "byte_size", "updated_at"}
    assert saved.headers["Cache-Control"] == "no-store"
    assert client.get("/api/resume/saved").json() == saved.json()
    reused = client.post("/api/resume/saved/skills?method=catalog")
    assert reused.json()["skills"] == ["Python", "SQL"]
    assert reused.headers["Cache-Control"] == "no-store"
    downloaded = client.get("/api/resume/saved/file")
    assert downloaded.content == make_pdf("Python SQL")
    assert downloaded.headers["Content-Type"] == "application/pdf"
    assert downloaded.headers["Content-Disposition"].startswith("attachment;")
    assert downloaded.headers["X-Content-Type-Options"] == "nosniff"
    assert downloaded.headers["Cache-Control"] == "no-store"
    assert upload(client, "Git", "new résumé.pdf").status_code == 200
    assert db_session.scalar(select(func.count()).select_from(SavedResume)) == 1
    assert client.post("/api/resume/saved/skills?method=catalog").json()["skills"] == ["Git"]
    assert "new%20r%C3%A9sum%C3%A9.pdf" in client.get("/api/resume/saved/file").headers["Content-Disposition"]
    assert client.delete("/api/resume/saved").status_code == 204
    for path in ("/api/resume/saved", "/api/resume/saved/file"):
        assert client.get(path).status_code == 404
    assert client.post("/api/resume/saved/skills").status_code == 404
    assert db_session.scalar(select(func.count()).select_from(SavedResume)) == 0


@pytest.mark.parametrize("content,media,status", [
    (b"invalid", "application/pdf", 422), (make_pdf(encrypted=True), "application/pdf", 422),
    (make_pdf(text=""), "application/pdf", 422), (make_pdf(pages=11), "application/pdf", 422),
    (make_pdf(), "text/plain", 415), (b"%PDF-" + b"x" * (5 * 1024 * 1024), "application/pdf", 413),
], ids=["invalid", "encrypted", "scanned", "pages", "media", "size"])
def test_invalid_replacement_keeps_original(authenticated_client, content, media, status):
    client = authenticated_client
    assert upload(client).status_code == 200
    response = client.put("/api/resume/saved", content=content, headers={"Content-Type": media})
    assert response.status_code == status
    assert client.get("/api/resume/saved/file").content == make_pdf("Python SQL")


def test_resume_is_private_and_user_deletion_cascades(authenticated_client, db_session):
    client = authenticated_client
    assert upload(client).status_code == 200
    owner_id = db_session.scalar(select(User.id))
    client.post("/api/auth/logout")
    assert client.post("/api/auth/register", json={"email": "other@example.com", "password": "Test-password-28"}).status_code == 201
    for path in ("/api/resume/saved", "/api/resume/saved/file"):
        assert client.get(path).status_code == 404
    assert client.post("/api/resume/saved/skills").status_code == 404
    assert client.delete("/api/resume/saved").status_code == 404
    assert upload(client, "Git").status_code == 200
    db_session.execute(delete(User).where(User.id == owner_id))
    db_session.commit()
    assert db_session.scalar(select(func.count()).select_from(SavedResume)) == 1
    assert client.post("/api/resume/saved/skills?method=catalog").json()["skills"] == ["Git"]


def test_filename_is_safe_and_skills_are_recomputed(authenticated_client, monkeypatch):
    from backend.app.api.routes import resume
    client = authenticated_client
    assert upload(client, filename="../../private\\resume\r\n.pdf").json()["filename"] == "resume.pdf"
    calls = []
    def predict(text, path):
        calls.append(text)
        return {"model": "test", "revision": "test", "experimental": True, "spans": []}
    monkeypatch.setattr(resume, "extract", predict)
    assert client.post("/api/resume/saved/skills").status_code == 200
    assert calls == ["Python SQL"]
