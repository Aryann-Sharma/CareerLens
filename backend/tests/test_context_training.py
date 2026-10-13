import hashlib
import json
import os
from pathlib import Path
import textwrap

import numpy as np
import pytest

from backend.ml.context_data import VARIANTS, expanded, load_cases, perturb
from backend.ml.train_context_review import LABELS, embed_cases, fit, metrics, predict
from backend.tests.varied_input_fixtures import document_bytes, FORMATS

DATA = Path("evaluation/context-training-cases.json")


def test_context_corpus_has_disjoint_families_and_real_source_provenance():
    rows = load_cases(DATA)
    assert len(rows) == 242
    assert {row["split"] for row in rows} == {"train", "dev", "test"}
    assert all(row["split"] == "test" for row in rows if row["origin"] != "project-authored")
    variants = expanded(rows)
    assert len(variants) == 1612
    assert len({row["id"] for row in variants}) == len(variants)
    normalized_splits = {}
    for row in variants:
        key = "".join(c.casefold() for c in row["text"] if c.isalnum())
        assert normalized_splits.setdefault(key, row["split"]) == row["split"]
    assert all(row["split"] == next(r["split"] for r in rows if r["id"] == row["base_id"]) for row in variants)
    source_ids = {source["id"] for source in json.loads(DATA.read_text())["sources"]}
    assert all(row["source_id"] in source_ids for row in rows if "source_id" in row)


@pytest.mark.skipif(os.getenv("RUN_CONTEXT_HEAD_TESTS") != "1", reason="Requires exported experimental weights")
@pytest.mark.parametrize("directory,report_name", [
    ("context-head-v1", "context-training-results.json"),
    ("context-head-clean-control", "context-clean-control-results.json"),
])
def test_exported_weights_reproduce_heldout_predictions(directory, report_name):
    from backend.app.services.semantic_matcher import _load_model
    from backend.app.services.model_assets import MODEL_REVISION
    root = Path(".models") / directory
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["sha256"] == hashlib.sha256((root / "weights.npz").read_bytes()).hexdigest()
    assert manifest["data_sha256"] == hashlib.sha256(DATA.read_bytes()).hexdigest()
    assert manifest["encoder_revision"] == MODEL_REVISION and manifest["labels"] == LABELS
    with np.load(root / "weights.npz", allow_pickle=False) as artifact:
        weights, bias = artifact["weights"], artifact["bias"]
    assert weights.shape == (384,24) and bias.shape == (24,)
    assert np.isfinite(weights).all() and np.isfinite(bias).all()
    rows = [r for r in expanded(load_cases(DATA)) if r["split"] == "test" and r["variant"] == "clean"]
    vectors, ranges = embed_cases(rows, _load_model()[0])
    actual = metrics(rows, predict(vectors, ranges, weights, bias, manifest["threshold"]))
    report = json.loads((Path("evaluation") / report_name).read_text())
    assert actual == report["evaluations"]["test-clean"]["candidate"]
    assert report["promotion_gate"]["passed"] is False


def test_conflicting_family_or_normalized_duplicate_split_is_rejected(tmp_path):
    row = {"id":"one","family":"one","split":"train","text":"Write application code.","expected":["Programming"],"acceptable":[]}
    for update in ({"family":"one","text":"A different sentence."}, {"family":"two","text":"WRITE application code!"}):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"cases":[row,{**row,**update,"id":"two","split":"test"}]}))
        with pytest.raises(ValueError, match="cross splits"):
            load_cases(path)


@pytest.mark.parametrize("kind", VARIANTS)
def test_typos_are_reproducible_and_preserve_negation(kind):
    text = "We do not require programming or negotiation."
    result = perturb(text, kind, "stable")
    assert result == perturb(text, kind, "stable")
    assert " do not " in result.casefold()
    if kind not in ("clean", "joined"):
        assert result != text


def test_ridge_fit_learns_weights_and_reduces_error_without_using_evaluation_rows():
    rng = np.random.default_rng(5)
    x = rng.normal(size=(100, 6))
    targets = x @ rng.normal(size=(6, 24)) + 0.3
    weights, bias = fit(x, targets, 0.01)
    assert np.mean((x @ weights + bias - targets) ** 2) < 0.001
    assert np.any(weights != 0)
    np.testing.assert_allclose(fit(x, targets, 0.01)[0], weights)
    assert predict(np.zeros((0,6)), [(0,0)], weights, bias, .3) == [[]]


def test_metrics_count_abstention_and_unsupported_suggestions():
    rows = [{"id":"a","expected":["Programming"],"acceptable":["Debugging"]},
            {"id":"b","expected":[],"acceptable":[]}]
    result = metrics(rows, [["Programming","Debugging"],["Empathy"]])
    assert result["covered"] == 1 and result["unsupported"] == 1
    assert result["negative_errors"] == 1 and result["negative_cases"] == 1


STRESS_CASES = expanded([r for r in load_cases(DATA) if r["split"] == "test"])


@pytest.mark.skipif(os.getenv("RUN_CONTEXT_STRESS_TESTS") != "1", reason="Requires real local extractor and sentence weights")
@pytest.mark.parametrize("case", STRESS_CASES, ids=lambda r:r["id"])
def test_real_preview_with_varied_context_and_typos(client, case):
    response = client.post("/api/preview", json={"job_description":case["text"],"user_skills":[],
        "extraction_method":"trained","matching_method":"semantic","interpret_duties":True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["match_score"] == 0 and body["matched_skills"] == []
    assert body["missing_skills"] == body["extracted_skills"]
    details = body["extraction_details"]
    for item in details["spans"] + details["context_suggestions"]:
        evidence = item.get("evidence", item.get("text"))
        assert case["text"][item["start"]:item["end"]] == evidence
    for check in details["spelling"]:
        assert case["text"][check["start"]:check["end"]] == check["original"]
    assert len(details["context_suggestions"]) <= 6


@pytest.mark.skipif(os.getenv("RUN_CONTEXT_STRESS_TESTS") != "1", reason="Requires real local extractor and sentence weights")
@pytest.mark.parametrize("format,media", FORMATS)
@pytest.mark.parametrize("text", [
    "Your job is to herd project cats: coordinate colleagues and track delivery milestones.",
    "Debug the applcation when it throws a tantrum. Trace the crash and repair the faulty code.",
    "Write useful social posts. Benefits: free coffee, a competitive salary and optional pottery lessons.",
])
def test_indirect_and_misspelled_document_round_trip(client, format, media, text):
    displayed = "\n".join(textwrap.wrap(text, width=55))
    route = "/api/job-pdf" if format == "PDF" else "/api/job-image"
    uploaded = client.post(route, content=document_bytes(displayed, format), headers={"Content-Type":media})
    assert uploaded.status_code == 200, uploaded.text
    imported = uploaded.json()
    assert imported["text"].strip() and imported["full_text"].strip()
    response = client.post("/api/preview", json={"job_description":imported["text"], "user_skills":[],
        "extraction_method":"trained", "interpret_duties":True})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["match_score"] == 0
    for suggestion in result["extraction_details"]["context_suggestions"]:
        assert imported["text"][suggestion["start"]:suggestion["end"]] == suggestion["evidence"]
