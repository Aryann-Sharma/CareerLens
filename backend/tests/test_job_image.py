from io import BytesIO
import socket
import subprocess
from threading import BoundedSemaphore
from types import SimpleNamespace

from PIL import Image
import pytest
from sqlalchemy import func, select

from backend.app.models import AnalysisRecord, SavedResume
from backend.app.services import image_worker, job_image
from backend.tests.image_fixtures import make_image


@pytest.mark.parametrize("retry,accepted", [
    ("we want a diligent team worker who is also passionate", True),
    ("we want a different team worker who is also passionate", False),
    ("we want a diligent team worker", False),
    ("", False),
])
def test_spacing_retry_cannot_change_letters_or_drop_text(retry, accepted):
    original = "wewantadiligentteamworkerwhoisalsopassionate"
    assert image_worker.restore_spacing(original, retry) == (retry if accepted else original)


@pytest.mark.parametrize("format,media", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")])
def test_real_image_import_is_public_unsaved_and_readable(client, db_session, format, media):
    result = client.post("/api/job-image", content=make_image(format=format), headers={"Content-Type": media})
    assert result.status_code == 200
    assert "Python" in result.json()["text"] and "SQL" in result.json()["text"]
    assert result.headers["Cache-Control"] == "no-store"
    assert db_session.scalar(select(func.count()).select_from(AnalysisRecord)) == 0
    assert db_session.scalar(select(func.count()).select_from(SavedResume)) == 0


def test_real_recognition_does_not_use_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Image recognition must not use the network")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    text = image_worker.recognize(image_worker.load_image(make_image()))
    assert "Python" in text


@pytest.mark.parametrize("content,message", [
    (b"not an image", "could not be read"), (make_image(format="GIF"), "PNG, JPEG"),
    (make_image(size=(20, 20)), "too small"), (make_image(size=(8001, 32)), "too large"),
    (make_image(size=(4000, 3001)), "too large"), (make_image(text=""), "No readable text"),
], ids=["invalid", "unsupported", "tiny", "long-side", "pixel-limit", "blank"])
def test_bad_images_return_useful_errors(client, content, message):
    response = client.post("/api/job-image", content=content, headers={"Content-Type": "image/png"})
    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_image_upload_type_and_size_limits(client):
    assert client.post("/api/job-image", content=make_image()).status_code == 415
    assert client.post("/api/job-image", content=b"x" * (image_worker.MAX_BYTES + 1), headers={"Content-Type": "image/png"}).status_code == 413


def test_animated_image_is_rejected():
    output = BytesIO()
    frames = [Image.new("RGB", (100, 100), color) for color in ("white", "black")]
    frames[0].save(output, format="PNG", save_all=True, append_images=frames[1:], duration=100)
    with pytest.raises(ValueError, match="still image"):
        image_worker.load_image(output.getvalue())


def test_exif_rotation_and_transparency_are_handled():
    exif = Image.Exif()
    exif[274] = 6
    rotated = image_worker.load_image(make_image(size=(100, 200), format="JPEG", exif=exif))
    assert rotated.size == (200, 100)
    output = BytesIO()
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(output, format="PNG")
    assert image_worker.load_image(output.getvalue()).getpixel((0, 0)) == (255, 255, 255)


def test_timeout_releases_slot_and_allows_retry(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("image reader", 30)
    monkeypatch.setattr(job_image.subprocess, "run", timeout)
    with pytest.raises(job_image.ImageReadError, match="too long"):
        job_image.read_job_image(make_image())
    monkeypatch.setattr(job_image.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b'{"text":"Python"}'))
    assert job_image.read_job_image(make_image()) == {"text": "Python"}


def test_busy_and_unavailable_readers_return_retryable_errors(client, monkeypatch):
    monkeypatch.setattr(job_image, "_slots", BoundedSemaphore(0))
    response = client.post("/api/job-image", content=make_image(), headers={"Content-Type": "image/png"})
    assert response.status_code == 503
    assert "busy" in response.json()["detail"]
    monkeypatch.setattr(job_image, "_slots", BoundedSemaphore(2))
    monkeypatch.setattr(job_image.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b'{"error":"Image reading is unavailable.","unavailable":true}'))
    assert client.post("/api/job-image", content=make_image(), headers={"Content-Type": "image/png"}).status_code == 503
