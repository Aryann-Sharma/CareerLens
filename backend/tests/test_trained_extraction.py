import os
from pathlib import Path
import socket

import pytest

from backend.app.api.routes import extraction
from backend.ml.predict import ExtractorUnavailableError, extract, load_assets


def test_extraction_is_available_without_login(client, monkeypatch):
    monkeypatch.setattr(extraction, "extract", lambda *args: {
        "model": "test", "revision": "test", "experimental": True, "spans": [],
    })
    assert client.post("/api/extract", json={"job_description": "Python"}).status_code == 200


@pytest.mark.parametrize("description", ["", " ", "x" * 50_001], ids=["empty", "blank", "too-long"])
def test_extraction_rejects_invalid_description(authenticated_client, description):
    response = authenticated_client.post("/api/extract", json={"job_description": description})
    assert response.status_code == 422


def test_extraction_is_a_private_unsaved_preview(authenticated_client, monkeypatch):
    result = {"model": "skillspan-crf-v1", "revision": "test", "experimental": True,
              "spans": [{"text": "Python", "label": "knowledge", "start": 0, "end": 6}]}
    monkeypatch.setattr(extraction, "extract", lambda *args: result)
    response = authenticated_client.post("/api/extract", json={"job_description": "Python"})
    assert response.status_code == 200
    assert response.json() == result
    assert authenticated_client.get("/api/analyses").json()["total"] == 0


def test_unavailable_extractor_does_not_break_exact_matching(authenticated_client, monkeypatch):
    def unavailable(*args):
        raise ExtractorUnavailableError("Missing files")
    monkeypatch.setattr(extraction, "extract", unavailable)
    response = authenticated_client.post("/api/extract", json={"job_description": "Python"})
    assert response.status_code == 503
    result = authenticated_client.post("/api/analyze", json={
        "job_description": "Python", "user_skills": ["Python"], "matching_method": "exact",
    })
    assert result.status_code == 200 and result.json()["match_score"] == 100


@pytest.mark.skipif(os.getenv("RUN_EXTRACTOR_TESTS") != "1", reason="Requires locally trained weights")
def test_trained_model_runs_offline_and_preserves_text_offsets(monkeypatch):
    def network_forbidden(*args, **kwargs):
        raise AssertionError("Inference must not access the network")
    monkeypatch.setattr(socket.socket, "connect", network_forbidden)
    load_assets.cache_clear()
    text = "Experience with Python and SQL. Excellent communication skills."
    first = extract(text, Path(".models/skillspan-crf"))
    assert first == extract(text, Path(".models/skillspan-crf"))
    assert first["spans"]
    for span in first["spans"]:
        assert text[span["start"]:span["end"]] == span["text"]
