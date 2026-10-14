"""Compare exact matching with the local model on labelled development examples."""

import argparse
import hashlib
import json
from pathlib import Path

from backend.app.services.model_assets import MODEL_NAME, MODEL_REVISION
from backend.app.services.semantic_matcher import (
    SIMILARITY_MARGIN, SIMILARITY_THRESHOLD, eligible_semantic_phrase, rank_skills,
)
from backend.app.services.skill_extractor import SKILL_ALIASES, canonicalize_skill


def metrics(rows: list[dict], predictions: list[str | None]) -> dict:
    true_positive = false_positive = false_negative = correct = 0
    errors = []
    for row, predicted in zip(rows, predictions):
        expected = row["expected"]
        correct += predicted == expected
        true_positive += predicted is not None and predicted == expected
        false_positive += predicted is not None and predicted != expected
        false_negative += expected is not None and predicted != expected
        if predicted != expected:
            errors.append({**row, "predicted": predicted})
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0
    return {
        "examples": len(rows), "correct": correct,
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("evaluation/skill_phrases.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/results.json"))
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.data.read_text(encoding="utf-8").splitlines() if line]
    assert all(row["expected"] is None or row["expected"] in SKILL_ALIASES for row in rows)
    rankings = rank_skills([row["phrase"] for row in rows])
    exact = [canonicalize_skill(row["phrase"]) for row in rows]
    exact = [skill if skill in SKILL_ALIASES else None for skill in exact]

    def predictions(threshold: float, margin: float) -> list[str | None]:
        result = []
        for row, baseline, ranking in zip(rows, exact, rankings):
            name, similarity = ranking[0]
            accepted = (eligible_semantic_phrase(row["phrase"])
                        and similarity >= threshold and similarity - ranking[1][1] >= margin)
            result.append(baseline or (name if accepted else None))
        return result

    semantic = predictions(SIMILARITY_THRESHOLD, SIMILARITY_MARGIN)
    report = {
        "model": MODEL_NAME, "revision": MODEL_REVISION,
        "data_sha256": hashlib.sha256(
            json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "threshold": SIMILARITY_THRESHOLD, "margin": SIMILARITY_MARGIN,
        "note": "Hand-authored development fixtures, not an independent real-world benchmark. No model training was performed.",
        "splits": {},
    }
    for split in ("calibration", "evaluation"):
        indices = [index for index, row in enumerate(rows) if row["split"] == split]
        subset = [rows[index] for index in indices]
        report["splits"][split] = {
            "exact": metrics(subset, [exact[index] for index in indices]),
            "semantic": metrics(subset, [semantic[index] for index in indices]),
        }
    # Report the development sweep without changing the application configuration.
    indices = [index for index, row in enumerate(rows) if row["split"] == "calibration"]
    report["calibration_sweep"] = []
    for threshold in (0.55, 0.6, 0.65, 0.7, 0.75):
        candidate = predictions(threshold, SIMILARITY_MARGIN)
        score = metrics([rows[index] for index in indices], [candidate[index] for index in indices])
        report["calibration_sweep"].append({
            "threshold": threshold, **{key: value for key, value in score.items() if key != "errors"},
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for split, scores in report["splits"].items():
        for method, score in scores.items():
            print(f"{split} {method}: {score['correct']}/{score['examples']} correct, "
                  f"precision={score['precision']}, recall={score['recall']}, F1={score['f1']}")


if __name__ == "__main__":
    main()
