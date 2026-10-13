"""Fit and evaluate a small context head without replacing application weights.

The sentence encoder is frozen. Ridge regression learns one output per capability
from project-labelled examples, including spelling augmentation. Development data
selects regularization and the review threshold; test data is read only afterward.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from backend.app.services.context_suggestions import CAPABILITIES, evidence_units, suggest_from_context
from backend.app.services.semantic_matcher import _load_model
from backend.app.services.model_assets import MODEL_REVISION
from backend.ml.context_data import expanded, load_cases

LABELS = list(CAPABILITIES)
REGULARIZATIONS = (0.1, 1.0, 10.0)
THRESHOLDS = (0.25, 0.35, 0.45, 0.55, 0.65, 0.75)


def write_report(path, report):
    """Keep each prediction on one line so the complete audit stays reviewable."""
    def render(value, depth=0):
        if isinstance(value, dict) and value and not {"id", "predicted"} <= value.keys():
            lines = [" " * (depth + 2) + json.dumps(key) + ": " + render(item, depth + 2)
                     for key, item in value.items()]
            return "{\n" + ",\n".join(lines) + "\n" + " " * depth + "}"
        if isinstance(value, list) and value and any(isinstance(item, (list, dict)) for item in value):
            return "[\n" + ",\n".join(" " * (depth + 2) + render(item, depth + 2) for item in value) + "\n" + " " * depth + "]"
        return json.dumps(value)
    path.write_text(render(report) + "\n", encoding="utf-8")


def fit(x, y, regularization):
    mean_x, mean_y = x.mean(axis=0), y.mean(axis=0)
    centered = x - mean_x
    weights = np.linalg.solve(centered.T @ centered + regularization * np.eye(x.shape[1]),
                              centered.T @ (y - mean_y))
    return weights, mean_y - mean_x @ weights


def metrics(rows, predictions):
    accepted = expected_total = covered = unsupported = negative_errors = negatives = 0
    details = []
    for row, predicted in zip(rows, predictions, strict=True):
        wanted, allowed = set(row["expected"]), set(row["acceptable"]) | set(row["expected"])
        predicted = set(predicted)
        missing, extra = wanted - predicted, predicted - allowed
        accepted += len(predicted)
        expected_total += len(wanted)
        covered += len(wanted & predicted)
        unsupported += len(extra)
        negatives += int(not allowed)
        negative_errors += int(not allowed and bool(predicted))
        details.append({"id": row["id"], "predicted": sorted(predicted), "missing": sorted(missing), "unsupported": sorted(extra)})
    precision = (accepted - unsupported) / accepted if accepted else 0.0
    recall = covered / expected_total if expected_total else 0.0
    return {"cases": len(rows), "suggestions": accepted, "unsupported": unsupported,
            "expected": expected_total, "covered": covered, "precision": round(precision, 4),
            "coverage": round(recall, 4), "f0_5": round(1.25 * precision * recall / max(.25 * precision + recall, 1e-12), 4),
            "negative_cases": negatives, "negative_errors": negative_errors, "results": details}


def embed_cases(rows, encoder):
    texts, ranges = [], []
    for row in rows:
        units = evidence_units(row["text"])
        start = len(texts)
        texts.extend(unit["text"] for unit in units)
        ranges.append((start, len(texts)))
    vectors = np.array(list(encoder.embed(texts, batch_size=32)), dtype=np.float64) if texts else np.empty((0, 384))
    return vectors, ranges


def predict(vectors, ranges, weights, bias, threshold):
    scores = vectors @ weights + bias
    predictions = []
    for start, end in ranges:
        best = scores[start:end].max(axis=0) if end > start else np.full(len(LABELS), -1.0)
        indices = np.argsort(-best)[:6]
        predictions.append([LABELS[j] for j in indices if best[j] >= threshold])
    return predictions


def baseline(rows):
    return [[s["skill"] for s in suggest_from_context(row["text"], [])[0]] for row in rows]


def run(data, output, report_path, augment=True):
    if output.exists():
        raise ValueError("Choose a fresh output directory")
    rows = load_cases(data)
    splits = {name: expanded([r for r in rows if r["split"] == name]) for name in ("train", "dev", "test")}
    encoder, _, _ = _load_model()
    # Fit only whole training sentences. All their perturbations keep the label.
    train = splits["train"] if augment else [r for r in splits["train"] if r["variant"] == "clean"]
    x = np.array(list(encoder.embed([r["text"] for r in train], batch_size=32)), dtype=np.float64)
    y = np.array([[float(label in row["expected"]) for label in LABELS] for row in train])
    dev_vectors, dev_ranges = embed_cases(splits["dev"], encoder)
    best = None
    experiments = []
    for regularization in REGULARIZATIONS:
        weights, bias = fit(x, y, regularization)
        for threshold in THRESHOLDS:
            result = metrics(splits["dev"], predict(dev_vectors, dev_ranges, weights, bias, threshold))
            experiments.append({"regularization": regularization, "threshold": threshold, **{k:v for k,v in result.items() if k != "results"}})
            # Require high development precision before maximizing coverage.
            rank = (result["precision"] >= .90, result["f0_5"], result["precision"], threshold)
            if best is None or rank > best[0]:
                best = (rank, weights, bias, regularization, threshold)
    _, weights, bias, regularization, threshold = best
    output.mkdir(parents=True)
    np.savez_compressed(output / "weights.npz", weights=weights, bias=bias)
    digest = hashlib.sha256((output / "weights.npz").read_bytes()).hexdigest()
    manifest = {"labels": LABELS, "encoder_revision": MODEL_REVISION, "sha256": digest,
                "regularization": regularization, "threshold": threshold, "data_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
                "training_rows": len(train), "typo_augmentation": augment,
                "status": "experimental; not loaded by the application"}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Selected alpha={regularization}, threshold={threshold}; evaluating untouched cases", flush=True)
    report = {"scope": "Project-authored labels and source paraphrases; no independent expert annotation. Encoder frozen; ridge head trained with typo augmentation.",
              "manifest": manifest, "base_counts": dict(Counter(r["split"] for r in rows)),
              "expanded_counts": {k:len(v) for k,v in splits.items()}, "selection": experiments, "evaluations": {}}
    for name in ("dev", "test"):
        vectors, ranges = embed_cases(splits[name], encoder)
        candidate_predictions = predict(vectors, ranges, weights, bias, threshold)
        baseline_predictions = baseline(splits[name])
        for kind in ("all", "clean", "deletion", "transposition", "duplication", "joined", "spacing", "casing"):
            indices = [i for i,r in enumerate(splits[name]) if kind == "all" or r["variant"] == kind]
            selected = [splits[name][i] for i in indices]
            report["evaluations"][f"{name}-{kind}"] = {
                "baseline": metrics(selected, [baseline_predictions[i] for i in indices]),
                "candidate": metrics(selected, [candidate_predictions[i] for i in indices])}
        print(name, {engine:{k:v for k,v in report['evaluations'][f'{name}-all'][engine].items() if k!='results'} for engine in ('baseline','candidate')}, flush=True)
    # Existing cases are regression checks, not training or selection examples.
    old = []
    for filename in ("context-cases.json", "context-holdout.json"):
        old.extend(json.loads((data.parent / filename).read_text(encoding="utf-8"))["cases"])
    old_vectors, old_ranges = embed_cases(old, encoder)
    report["evaluations"]["previous-regressions"] = {
        "baseline": metrics(old, baseline(old)),
        "candidate": metrics(old, predict(old_vectors, old_ranges, weights, bias, threshold))}
    gates = []
    for key in ("test-all", "test-clean", "previous-regressions"):
        results = report["evaluations"][key]
        a, b = results["candidate"], results["baseline"]
        gates.append(a["precision"] >= max(.90, b["precision"]) and a["coverage"] >= b["coverage"] and a["negative_errors"] <= b["negative_errors"])
    report["promotion_gate"] = {"passed": all(gates), "rule": "Candidate precision >= max(90%, baseline), coverage >= baseline, and negative errors <= baseline on test-all, test-clean, and previous regressions. No automatic deployment."}
    write_report(report_path, report)
    print(report["promotion_gate"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("evaluation/context-training-cases.json"))
    parser.add_argument("--output", type=Path, default=Path(".models/context-head-v1"))
    parser.add_argument("--report", type=Path, default=Path("evaluation/context-training-results.json"))
    parser.add_argument("--no-augmentation", action="store_true", help="Run the clean-only training control")
    args = parser.parse_args()
    run(args.data, args.output, args.report, augment=not args.no_augmentation)
