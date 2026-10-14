"""Train a small supervised role classifier from official occupational labels."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from backend.ml.role_data import FILES, dataset
from backend.ml.role_model import FEATURE_SIZE, FEATURE_VERSION, LABELS, ROLE_CODES, features, probabilities


def metrics(scores, targets, threshold=0, margin=0):
    pred = scores.argmax(axis=1)
    counts = {}
    for index, label in enumerate(LABELS):
        tp = int(((pred == index) & (targets == index)).sum())
        fp = int(((pred == index) & (targets != index)).sum())
        fn = int(((pred != index) & (targets == index)).sum())
        counts[label] = {"support": int((targets == index).sum()), "precision": tp / max(1, tp + fp),
                         "recall": tp / max(1, tp + fn), "f1": 2 * tp / max(1, 2 * tp + fp + fn)}
    sorted_scores = np.sort(scores, axis=1)
    accepted = (pred != LABELS.index("other")) & (sorted_scores[:, -1] >= threshold) & (sorted_scores[:, -1] - sorted_scores[:, -2] >= margin)
    return {"accuracy": float((pred == targets).mean()), "macro_f1": float(np.mean([r["f1"] for r in counts.values()])),
            "per_label": counts, "accepted": int(accepted.sum()),
            "accepted_precision": float((pred[accepted] == targets[accepted]).mean()) if accepted.any() else None,
            "coverage": float(accepted.mean())}


def run(data: Path, output: Path, report_path: Path):
    import torch
    torch.set_num_threads(2)
    torch.manual_seed(42)
    if output.exists():
        raise ValueError("Choose a new output directory; existing models are never overwritten")
    splits, audit = dataset(data)
    matrices = {name: np.stack([features(row["text"]) for row in rows]) for name, rows in splits.items()}
    targets = {name: np.array([LABELS.index(row["label"]) for row in rows]) for name, rows in splits.items()}
    report = {"source": "O*NET 31.0 Database", "source_sha256": FILES, "role_codes": ROLE_CODES,
              "training_files": ["occupation_data.csv", "job_titles.csv", "task_statements.csv"],
              "deployment": "Offline experiment only; not connected to application recommendations.",
              "audit": audit, "counts": {name: dict(Counter(row["label"] for row in rows)) for name, rows in splits.items()},
              "selection": "Best development macro F1 over three declared regularizations, checkpoints at epochs 20/40/60/80",
              "seed": 42, "features": FEATURE_VERSION, "experiments": []}
    x, y = torch.from_numpy(matrices["train"]), torch.from_numpy(targets["train"])
    sizes = np.bincount(targets["train"], minlength=len(LABELS))
    class_weights = torch.tensor(np.sqrt(len(y) / sizes), dtype=torch.float32)
    best = None
    for decay in (0.001, 0.01, 0.1):
        torch.manual_seed(42)
        model = torch.nn.Linear(FEATURE_SIZE, len(LABELS))
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.025, weight_decay=decay)
        for epoch in range(1, 81):
            order = torch.randperm(len(y))
            for batch in order.split(128):
                optimizer.zero_grad()
                loss = torch.nn.functional.cross_entropy(model(x[batch]), y[batch], weight=class_weights)
                loss.backward()
                optimizer.step()
            if epoch % 20 == 0:
                weights = model.weight.detach().numpy().copy()
                bias = model.bias.detach().numpy().copy()
                dev = metrics(probabilities(matrices["dev"], weights, bias), targets["dev"])
                report["experiments"].append({"weight_decay": decay, "epoch": epoch, "development": dev})
                print(f"decay={decay}, epoch={epoch}, development macro F1={dev['macro_f1']:.3f}", flush=True)
                if best is None or dev["macro_f1"] > best[0]:
                    best = (dev["macro_f1"], weights, bias, decay, epoch)
    _, weights, bias, decay, epoch = best
    dev_scores = probabilities(matrices["dev"], weights, bias)
    gates = []
    for threshold in (0.6, 0.7, 0.8, 0.9, 0.95):
        for margin in (0.15, 0.25, 0.4):
            result = metrics(dev_scores, targets["dev"], threshold, margin)
            if result["accepted"] >= 10 and result["accepted_precision"] >= 0.95:
                gates.append((result["accepted"], threshold, margin))
    _, threshold, margin = max(gates, default=(0, 1.0, 1.0))
    output.mkdir(parents=True)
    np.savez_compressed(output / "weights.npz", weights=weights, bias=bias)
    digest = hashlib.sha256((output / "weights.npz").read_bytes()).hexdigest()
    manifest = {"revision": digest[:12], "features": FEATURE_VERSION, "labels": LABELS, "sha256": digest,
                "threshold": threshold, "margin": margin, "source": "O*NET 31.0 Database"}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    report["selected"] = {"weight_decay": decay, "epoch": epoch, **manifest}
    report["development"] = metrics(dev_scores, targets["dev"], threshold, margin)
    report["test"] = metrics(probabilities(matrices["test"], weights, bias), targets["test"], threshold, margin)
    report["majority_baseline_accuracy"] = float((targets["test"] == LABELS.index("other")).mean())
    # A predefined robustness check, not additional training data.
    def typo(text):
        words = text.split()
        for i, word in enumerate(words):
            if len(word) >= 6 and word.isalpha():
                words[i] = word[:2] + word[3] + word[2] + word[4:]
                break
        return " ".join(words)
    typo_matrix = np.stack([features(typo(row["text"])) for row in splits["test"]])
    report["test_with_one_transposition"] = metrics(probabilities(typo_matrix, weights, bias), targets["test"], threshold, margin)
    report["limitations"] = ["Occupation titles and tasks, not labelled job advertisements.",
        "Five broad computing directions plus other; only group-normalized exact duplicates are removed.",
        "Same-source held-out evaluation; related title variants can remain across splits.",
        "Scores are not calibrated probabilities. The experiment is not used in the application."]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"test": report["test"], "threshold": threshold, "margin": margin}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path(".data/onet-31.0"))
    parser.add_argument("--output", type=Path, default=Path(".models/onet-roles"))
    parser.add_argument("--report", type=Path, default=Path("evaluation/role-results.json"))
    args = parser.parse_args()
    run(args.data, args.output, args.report)
