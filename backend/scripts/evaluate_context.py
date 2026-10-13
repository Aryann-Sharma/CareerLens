"""Report review suggestion coverage without treating regression fixtures as gold data."""

import json
import argparse
from pathlib import Path

from backend.app.services.context_suggestions import suggest_from_context


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=Path("evaluation/context-cases.json"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/context-results.json"))
    args = parser.parse_args()
    source = args.cases
    data = json.loads(source.read_text(encoding="utf-8"))
    rows = []
    for case in data["cases"]:
        suggestions, _ = suggest_from_context(case["text"], [])
        predicted = {s["skill"] for s in suggestions}
        expected, acceptable = set(case["expected"]), set(case["acceptable"])
        rows.append({"id": case["id"], "group": case.get("group", "holdout"), "predicted": sorted(predicted),
                     "missing": sorted(expected - predicted), "unsupported": sorted(predicted - expected - acceptable)})
    expected_count = sum(len(c["expected"]) for c in data["cases"])
    predictions = sum(len(row["predicted"]) for row in rows)
    result = {"scope": data["description"], "cases": len(rows),
              "suggestion_precision": round(1 - sum(len(r["unsupported"]) for r in rows) / max(predictions, 1), 4),
              "expected_coverage": round(1 - sum(len(r["missing"]) for r in rows) / max(expected_count, 1), 4), "results": rows}
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
