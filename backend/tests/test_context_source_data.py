import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest

from backend.ml.context_data import expanded, load_cases
from backend.ml.context_source_data import ACTIVITIES, occupation_split, source_rows, task_cases
from backend.ml.train_context_review import LABELS, balanced_weights, embed_cases, fit, metrics, predict, write_report

DATA = Path("evaluation/context-source-cases.json")
ROWS = load_cases(DATA)
FINAL_ROWS = load_cases(Path("evaluation/context-final-check.json"))


def test_sources_occupations_and_variants_do_not_cross_splits():
    occupations, families, texts = {}, {}, {}
    for row in ROWS:
        assert families.setdefault(row["family"], row["split"]) == row["split"]
        for code in row.get("occupations", []):
            assert occupations.setdefault(code, row["split"]) == row["split"] == occupation_split(code)
        if row["origin"] == "public-source-paraphrase":
            assert row["split"] == "test" and row["family"] == row["source_id"]
    for row in expanded(ROWS):
        key = "".join(c.casefold() for c in row["text"] if c.isalnum())
        assert texts.setdefault(key, row["split"]) == row["split"]
    previous = load_cases(Path("evaluation/context-training-cases.json"))
    assert not {r["id"] for r in previous if r["split"] == "test"} & {r["id"] for r in ROWS}
    assert len([r for r in ROWS if r["origin"] == "onet-activity-crosswalk"]) == 437
    assert len(ROWS) == 748


def test_annotation_changes_and_provenance_are_auditable():
    data = json.loads(DATA.read_text())
    audit_path = Path("evaluation/context-source-label-audit.json")
    changes = json.loads(audit_path.read_text())["changes"]
    assert data["audit"]["label_audit_sha256"] == hashlib.sha256(audit_path.read_text(encoding="utf-8").encode()).hexdigest()
    sources = {s["id"] for s in data["sources"]}
    assert all(r["source_id"] in sources for r in ROWS if "source_id" in r)
    ids = {r["id"] for r in ROWS}
    for id, change in changes.items():
        assert change["reason"]
        if change.get("exclude"):
            assert id not in ids
        else:
            row = next(r for r in ROWS if r["id"] == id)
            assert row["expected"] == change["expected"] and row["annotation_note"] == change["reason"]
    assert all(set(labels) <= set(LABELS) for labels in ACTIVITIES.values())


def test_final_sources_are_separate_from_training_and_development():
    sources = {r.get("source_id") for r in ROWS}
    assert all(r["split"] == "test" and r["source_id"] not in sources for r in FINAL_ROWS)
    assert len({r["source_id"] for r in FINAL_ROWS}) == 3
    assert len(FINAL_ROWS) == 12


def test_wrong_source_checksum_is_rejected(tmp_path):
    path = tmp_path / "tasks.csv"
    path.write_text("Task,wrong data\n")
    with pytest.raises(ValueError, match="checksum"):
        source_rows(path)


def test_report_can_be_written_to_a_fresh_output_directory(tmp_path):
    target = tmp_path / "reports" / "context" / "result.json"
    report = {"cases": 1, "results": [{"id":"sample", "predicted":["Programming"]}]}
    write_report(target, report)
    assert json.loads(target.read_text()) == report


def test_unknown_tasks_are_not_labelled_as_negative_and_shared_tasks_are_removed():
    codes = {}
    for i in range(100):
        code = f"15-{i:04}.00"
        codes.setdefault(occupation_split(code), code)
    def row(text, code, activity="4.A.3.b.1.a.3"):
        return {"Task":text,"Task ID":"1","O*NET-SOC Code":code,"DWA Element ID":activity}
    rows = [row("Write new application code.", codes["train"]),
            row("Write new application code.", codes["test"]),
            row("Repair a wooden cabinet.", codes["train"], "unmapped"),
            row("Implement source code for the billing application.", codes["train"])]
    selected, audit = task_cases(rows)
    assert len(selected) == 1 and selected[0]["expected"] == ["Programming"]
    assert audit["cross_split_duplicate_groups_removed"] == 1


def test_balancing_uses_training_labels_and_weighted_fit_is_reproducible():
    targets = np.array([[1.,0.], [1.,0.], [1.,0.], [0.,1.], [0.,0.]])
    weights = balanced_weights(targets)
    assert weights[3] == pytest.approx(weights[:3].sum())
    assert weights[4] == pytest.approx(weights[3]) and weights.mean() == pytest.approx(1.)
    x = np.arange(15).reshape(5,3)
    np.testing.assert_allclose(fit(x,targets,1.)[0], fit(x,targets,1.,np.ones(5))[0])
    assert np.isfinite(fit(x,targets,1.,weights)[0]).all()


@pytest.mark.skipif(os.getenv("RUN_SOURCE_HEAD_TESTS") != "1", reason="Requires exported source-trained weights")
@pytest.mark.parametrize("directory, report", [("context-head-source-v4", "context-source-results.json"),
    ("context-head-source-balanced-v4", "context-source-balanced-results.json")])
def test_source_head_reproduces_test_predictions(directory, report):
    from backend.app.services.semantic_matcher import _load_model
    from backend.app.services.model_assets import MODEL_REVISION
    root = Path(".models") / directory
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["encoder_revision"] == MODEL_REVISION and manifest["labels"] == LABELS
    assert manifest["data_sha256"] == hashlib.sha256(DATA.read_bytes()).hexdigest()
    assert manifest["sha256"] == hashlib.sha256((root / "weights.npz").read_bytes()).hexdigest()
    with np.load(root / "weights.npz", allow_pickle=False) as archive:
        weights, bias = archive["weights"], archive["bias"]
    assert weights.shape == (384, 24) and bias.shape == (24,)
    assert np.isfinite(weights).all() and np.isfinite(bias).all()
    rows = [r for r in expanded(ROWS) if r["split"] == "test" and r["variant"] == "clean"]
    vectors, ranges = embed_cases(rows, _load_model()[0])
    actual = metrics(rows, predict(vectors, ranges, weights, bias, manifest["threshold"]))
    recorded = json.loads((Path("evaluation") / report).read_text())
    assert actual == recorded["evaluations"]["test-clean"]["candidate"]
    assert "previous-test-regressions" in recorded["promotion_gate"]["evaluated_sets"]


@pytest.mark.skipif(os.getenv("RUN_CONTEXT_STRESS_TESTS") != "1", reason="Requires actual local extraction and matching weights")
@pytest.mark.parametrize("case", expanded([r for r in ROWS if r["split"] == "test"]), ids=lambda r:r["id"])
def test_new_source_inputs_through_preview(client, case):
    response = client.post("/api/preview", json={"job_description":case["text"],
        "user_skills":[],"extraction_method":"trained","matching_method":"semantic","interpret_duties":True})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["match_score"] == 0 and result["matched_skills"] == []
    assert result["missing_skills"] == result["extracted_skills"]
    details = result["extraction_details"]
    for item in details["spans"] + details["context_suggestions"]:
        assert case["text"][item["start"]:item["end"]] == item.get("evidence", item.get("text"))
    for item in details["spelling"]:
        assert case["text"][item["start"]:item["end"]] == item["original"]
        assert all(c.casefold() != item["original"].casefold() for c in item["candidates"])
    assert len(details["context_suggestions"]) <= 6


@pytest.mark.skipif(os.getenv("RUN_CONTEXT_STRESS_TESTS") != "1", reason="Requires actual local extraction and matching weights")
@pytest.mark.parametrize("case", expanded(FINAL_ROWS), ids=lambda r:r["id"])
def test_final_source_inputs_through_preview(client, case):
    test_new_source_inputs_through_preview(client, case)


@pytest.mark.skipif(os.getenv("RUN_CONTEXT_STRESS_TESTS") != "1", reason="Requires document readers and actual local weights")
@pytest.mark.parametrize("format,media", [("PDF","application/pdf"),("PNG","image/png"),
    ("JPEG","image/jpeg"),("WEBP","image/webp")])
def test_conversational_heading_document_import(client, format, media):
    from backend.tests.varied_input_fixtures import document_bytes
    text = ("What you'll be doing:\nWrite Python code for web applications.\n"
        "Why you'll love it here:\nEnjoy optional presentation classes.")
    route = "/api/job-pdf" if format == "PDF" else "/api/job-image"
    uploaded = client.post(route, content=document_bytes(text, format), headers={"Content-Type":media})
    assert uploaded.status_code == 200, uploaded.text
    document = uploaded.json()
    assert "optional" in document["full_text"]
    if format == "JPEG":
        # This compressed fixture loses spaces in the heading and duty. Keep
        # that failure visible and exercise the same explicit preview edit as
        # a user; do not count it as a successful automatic section selection.
        assert not document["selection_applied"]
        assert document["text"] == document["full_text"]
        reviewed = "Write Python code for web applications."
    else:
        assert document["selection_applied"]
        assert "Python" in document["text"] and "optional" not in document["text"]
        reviewed = document["text"]
    result = client.post("/api/preview", json={"job_description":reviewed,
        "user_skills":["Python"], "extraction_method":"trained", "interpret_duties":True})
    assert result.status_code == 200, result.text
    assert "Python" in result.json()["matched_skills"]
    assert all(s["skill"] != "Presentation" for s in result.json()["extraction_details"]["context_suggestions"])
