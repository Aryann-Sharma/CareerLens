import subprocess
from threading import BoundedSemaphore

import pytest
from sqlalchemy import func, select

from backend.app.models import AnalysisRecord, SavedResume
from backend.app.services import resume
from backend.tests.pdf_fixtures import make_pdf
from backend.tests.image_fixtures import make_image
from backend.tests.test_job_document import POSTING


def post(client, content, media="application/pdf"):
    return client.post("/api/job-pdf", content=content, headers={"Content-Type": media})


def test_job_pdf_selects_role_sections_without_saving_or_analyzing(client, db_session):
    result = post(client, make_pdf(POSTING, pages=2))
    assert result.status_code == 200
    body = result.json()
    assert body["pages"] == 2 and body["selection_applied"]
    assert "Java" in body["full_text"] and "Java" not in body["text"]
    assert "Docker" in body["text"]
    assert result.headers["Cache-Control"] == "no-store"
    for model in (AnalysisRecord, SavedResume):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0
    analysis = client.post("/api/preview", json={"job_description": body["text"], "user_skills": ["Python", "SQL", "Git", "Docker"], "extraction_method": "catalog", "matching_method": "exact"})
    assert analysis.status_code == 200
    assert analysis.json()["match_score"] == 100
    assert set(analysis.json()["extracted_skills"]) == {"Python", "SQL", "Git", "Docker"}


@pytest.mark.parametrize("content,message", [
    (b"not pdf", "valid PDF"),
    (make_pdf(encrypted=True), "password protected"),
    (make_pdf(pages=11), "1 to 10 pages"),
    (make_pdf(text=""), "Scanned PDFs"),
    (make_pdf(text="x" * 50001), "too much text"),
], ids=["invalid", "encrypted", "pages", "scanned", "text-limit"])
def test_bad_job_pdf_returns_useful_error(client, content, message):
    result = post(client, content)
    assert result.status_code == 422
    assert message in result.json()["detail"]


def test_pdf_media_size_and_unstructured_text(client):
    assert post(client, make_pdf(), "image/png").status_code == 415
    assert post(client, b"x" * (5 * 1024 * 1024 + 1)).status_code == 413
    result = post(client, make_pdf(), "Application/PDF; charset=binary")
    assert result.status_code == 200
    assert result.json()["text"] == result.json()["full_text"] == "Python SQL Git"
    assert not result.json()["selection_applied"]


def test_timeout_and_busy_job_reader_can_recover(client, monkeypatch):
    from backend.app.api.routes import job_pdf
    monkeypatch.setattr(job_pdf, "_slots", BoundedSemaphore(0))
    assert post(client, make_pdf()).status_code == 503
    monkeypatch.setattr(job_pdf, "_slots", BoundedSemaphore(2))
    original = resume.subprocess.run
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("pdf", 12)
    monkeypatch.setattr(resume.subprocess, "run", timeout)
    for _ in range(3):
        result = post(client, make_pdf())
        assert result.status_code == 422 and "too long" in result.json()["detail"]
    monkeypatch.setattr(resume.subprocess, "run", original)
    assert post(client, make_pdf()).status_code == 200


def test_images_share_section_selection(client, monkeypatch):
    from backend.app.api.routes import job_image
    monkeypatch.setattr(job_image, "read_job_image", lambda _: {"text": POSTING})
    result = client.post("/api/job-image", content=b"fixture", headers={"Content-Type": "image/png"})
    assert result.status_code == 200
    assert result.json()["selection_applied"]
    assert result.json()["full_text"] == POSTING
    assert "Java" not in result.json()["text"]


def test_real_photo_of_full_posting_selects_requirements(client):
    text = "About us\nWe build Java tools.\nRequirements\nPython and SQL skills\nBenefits\nPaid leave"
    result = client.post("/api/job-image", content=make_image(text, size=(1000, 500)), headers={"Content-Type": "image/png"})
    assert result.status_code == 200
    body = result.json()
    assert body["selection_applied"]
    assert "Java" in body["full_text"] and "Java" not in body["text"]
    assert "Python" in body["text"] and "SQL" in body["text"]
