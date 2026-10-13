"""Check frozen experimental heads on additional source descriptions."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from backend.app.services.model_assets import MODEL_REVISION
from backend.app.services.semantic_matcher import _load_model
from backend.ml.context_data import expanded, load_cases
from backend.ml.train_context_review import LABELS, baseline, embed_cases, metrics, predict, write_report


def evaluate(data, directories, output):
    rows = expanded(load_cases(data))
    if any(r["split"] != "test" for r in rows):
        raise ValueError("Additional evaluation must contain only test cases")
    vectors, ranges = embed_cases(rows, _load_model()[0])
    predictions = {"baseline": baseline(rows)}
    manifests = {}
    for root in directories:
        manifest = json.loads((root / "manifest.json").read_text())
        if manifest["labels"] != LABELS or manifest["encoder_revision"] != MODEL_REVISION:
            raise ValueError("Incompatible experimental head")
        if hashlib.sha256((root / "weights.npz").read_bytes()).hexdigest() != manifest["sha256"]:
            raise ValueError("Experimental head checksum mismatch")
        with np.load(root / "weights.npz", allow_pickle=False) as artifact:
            weights, bias = artifact["weights"], artifact["bias"]
        if weights.shape != (384, len(LABELS)) or bias.shape != (len(LABELS),):
            raise ValueError("Unexpected experimental head dimensions")
        if not np.isfinite(weights).all() or not np.isfinite(bias).all():
            raise ValueError("Nonfinite experimental head")
        manifests[root.name] = manifest
        predictions[root.name] = predict(vectors, ranges, weights, bias, manifest["threshold"])
    report = {"scope": "Additional source paraphrases with project labels, collected after configurations were fixed. No model selection uses this report.",
        "data_sha256": hashlib.sha256(data.read_bytes()).hexdigest(), "manifests": manifests, "evaluations": {}}
    slices = {"all": list(range(len(rows))), "clean": [i for i,r in enumerate(rows) if r["variant"] == "clean"]}
    slices.update({source:[i for i,r in enumerate(rows) if r["source_id"] == source] for source in sorted({r["source_id"] for r in rows})})
    for name, indices in slices.items():
        selected = [rows[i] for i in indices]
        report["evaluations"][name] = {model:metrics(selected, [values[i] for i in indices]) for model,values in predictions.items()}
    write_report(output, report)
    print({model:{k:v for k,v in result.items() if k!='results'} for model,result in report['evaluations']['all'].items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("evaluation/context-final-check.json"))
    parser.add_argument("--models", nargs="+", type=Path, default=[Path(".models/context-head-source-v4"), Path(".models/context-head-source-balanced-v4")])
    parser.add_argument("--output", type=Path, default=Path("evaluation/context-final-results.json"))
    args = parser.parse_args()
    evaluate(args.data, args.models, args.output)
