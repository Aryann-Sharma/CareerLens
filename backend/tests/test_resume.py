import subprocess

import pytest
from sqlalchemy import func, select

from backend.app.models.analysis import AnalysisRecord
from backend.app.services import resume
from backend.app.services.pdf_worker import read_pdf
from backend.tests.pdf_fixtures import make_pdf


def test_guest_pdf_import_is_not_saved(client, db_session):
    result = client.post("/api/resume?method=catalog", content=make_pdf(), headers={"Content-Type": "application/pdf"})
    assert result.status_code == 200
    assert result.json()["skills"] == ["Python", "SQL", "Git"]
    assert result.json()["pages"] == 1
    assert db_session.scalar(select(func.count()).select_from(AnalysisRecord)) == 0


@pytest.mark.parametrize("content,message", [
    (b"not pdf", "valid PDF"),
    (make_pdf(encrypted=True), "password protected"),
    (make_pdf(pages=11), "1 to 10 pages"),
    (make_pdf(text=""), "Scanned PDFs"),
    (make_pdf(text="x" * 50_001), "too much text"),
], ids=["invalid", "encrypted", "too-many-pages", "scanned", "too-much-text"])
def test_invalid_pdf_returns_useful_error(client, content, message):
    response = client.post("/api/resume?method=catalog", content=content, headers={"Content-Type": "application/pdf"})
    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_pdf_upload_limits(client):
    assert client.post("/api/resume", content=b"text").status_code == 415
    response = client.post("/api/resume", content=b"%PDF-" + b"x" * (5 * 1024 * 1024), headers={"Content-Type": "application/pdf"})
    assert response.status_code == 413


def test_parse_timeout_is_handled(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("parser", 12)
    monkeypatch.setattr(resume.subprocess, "run", timeout)
    with pytest.raises(resume.ResumeError, match="too long"):
        resume.parse_pdf(make_pdf())


def test_trained_pdf_import(client, monkeypatch):
    from backend.app.api.routes import resume as route
    monkeypatch.setattr(route, "extract", lambda *args: {"model": "test", "revision": "test", "experimental": True, "spans": [
        {"text": "stakeholder communication", "label": "skill", "start": 0, "end": 25}
    ]})
    result = client.post("/api/resume", content=make_pdf("stakeholder communication"), headers={"Content-Type": "application/pdf"})
    assert result.status_code == 200
    assert result.json()["skills"] == ["stakeholder communication"]


def test_pdf_text_escapes_are_preserved():
    assert read_pdf(make_pdf("Python (advanced)"))["text"] == "Python (advanced)"
