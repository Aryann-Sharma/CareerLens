import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest

from backend.ml import role_data
from backend.ml.role_model import FEATURE_SIZE, FEATURE_VERSION, LABELS, features, load_model, probabilities, suggest_role
from backend.ml.train_roles import metrics


def artifact(root):
    weights = np.zeros((len(LABELS), FEATURE_SIZE), dtype=np.float32)
    bias = np.zeros(len(LABELS), dtype=np.float32)
    bias[LABELS.index("web")] = 8
    np.savez_compressed(root / "weights.npz", weights=weights, bias=bias)
    manifest = {"features": FEATURE_VERSION, "labels": LABELS, "threshold": 0.9, "margin": 0.3,
                "revision": "fixture", "sha256": hashlib.sha256((root / "weights.npz").read_bytes()).hexdigest()}
    (root / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def test_character_features_ignore_case_and_retain_similarity_after_typo():
    original = features("Web developer")
    assert np.array_equal(original, features("WEB DEVELOPER"))
    assert np.isclose(np.linalg.norm(original), 1)
    assert float(original @ features("Web developre")) > 0.5
    assert not features("🌳 !!!").any()
    assert np.array_equal(features("a" * 8000), features("a" * 8000 + " changed"))


def test_linear_weights_determine_prediction_and_empty_input_abstains(tmp_path):
    artifact(tmp_path)
    assert suggest_role("some text", tmp_path)["role_id"] == "web"
    assert suggest_role("!!!", tmp_path)["status"] == "uncertain"
    assert suggest_role("some text", tmp_path / "absent")["status"] == "unavailable"
    scores = probabilities(np.zeros((2, FEATURE_SIZE)), np.zeros((6, FEATURE_SIZE)), np.zeros(6))
    assert np.allclose(scores, 1 / 6)


@pytest.mark.parametrize("field,value", [("threshold", -1), ("margin", float("nan")), ("features", "wrong"), ("labels", ["wrong"]), ("sha256", "incorrect")])
def test_corrupted_or_incompatible_model_is_not_used(tmp_path, field, value):
    manifest = artifact(tmp_path)
    manifest[field] = value
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert suggest_role("web developer", tmp_path)["status"] == "unavailable"


def test_metrics_do_not_hide_missing_classes_and_report_abstention():
    scores = np.eye(6)[[5, 5, 4]]
    result = metrics(scores, np.array([5, 4, 4]), threshold=1, margin=1)
    assert result["accuracy"] == pytest.approx(2 / 3)
    assert result["per_label"]["data"]["f1"] == 0
    assert result["accepted"] == 1 and result["accepted_precision"] == 1


def test_group_split_removes_conflicts_and_case_punctuation_duplicates(monkeypatch, tmp_path):
    fixtures = {
        "job_titles.csv": [
            {"O*NET-SOC Code": "15-1254.00", "Job Title": "Web-Developer"},
            {"O*NET-SOC Code": "15-1254.00", "Job Title": "WEB DEVELOPER"},
            {"O*NET-SOC Code": "15-1252.00", "Job Title": "Shared title"},
            {"O*NET-SOC Code": "15-1254.00", "Job Title": "Shared title"}],
        "task_statements.csv": [], "occupation_data.csv": []}
    monkeypatch.setattr(role_data, "read_rows", lambda root, name: fixtures[name])
    splits, audit = role_data.dataset(tmp_path)
    rows = [row for split in splits.values() for row in split]
    assert len(rows) == 1 and rows[0]["label"] == "web"
    assert audit["conflicting_groups_removed"] == 1
    assert role_data.dataset(tmp_path)[0] == splits


def test_source_mismatch_rejected_before_csv_parsing(tmp_path):
    (tmp_path / "occupation_data.csv").write_text("bad data")
    with pytest.raises(ValueError, match="checksum"):
        role_data.read_rows(tmp_path, "occupation_data.csv")


@pytest.mark.skipif(os.getenv("RUN_ROLE_TESTS") != "1", reason="Requires local occupation data and trained role weights")
def test_real_source_split_and_artifact_match_recorded_experiment():
    splits, _ = role_data.dataset(Path(".data/onet-31.0"))
    groups = {name: {row["group"] for row in rows} for name, rows in splits.items()}
    assert not groups["train"] & groups["dev"]
    assert not groups["train"] & groups["test"]
    assert not groups["dev"] & groups["test"]
    weights, bias, manifest = load_model(str(Path(".models/onet-roles").resolve()))
    matrix = np.stack([features(row["text"]) for row in splits["test"]])
    targets = np.array([LABELS.index(row["label"]) for row in splits["test"]])
    actual = metrics(probabilities(matrix, weights, bias), targets, manifest["threshold"], manifest["margin"])
    report = json.loads(Path("evaluation/role-results.json").read_text())
    assert actual == report["test"]
    assert manifest["sha256"] == report["selected"]["sha256"]
