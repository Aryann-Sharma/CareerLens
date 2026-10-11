"""Summarize validation errors for the frozen contextual extractor."""

import argparse
from collections import Counter
import json
from pathlib import Path

from backend.ml.contextual import collect_predictions, empty_predictions, encode_rows, pad_batch
from backend.ml.contextual_predict import load_assets
from backend.ml.data import HEADS, clean_splits, load_split
from backend.ml.features import bio_spans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path(".models/skillspan-distilbert"))
    parser.add_argument("--report", type=Path, default=Path("evaluation/development-errors.json"))
    args = parser.parse_args()
    splits, _ = clean_splits({split: load_split(Path(f".data/skillspan/{split}.json")) for split in ("train", "dev", "test")})
    rows = splits["dev"]
    _, revision, tokenizer, session, lock = load_assets(args.model.resolve())
    predictions = empty_predictions(rows)
    with lock:
        chunks = encode_rows(tokenizer, rows)
        for start in range(0, len(chunks), 8):
            batch = chunks[start:start + 8]
            arrays = pad_batch(batch)
            logits = session.run(None, {key: arrays[key] for key in ("input_ids", "attention_mask")})[0]
            collect_predictions(predictions, batch, logits)
    report = {"model_revision": revision, "split": "development", "sentences": len(rows), "heads": {}}
    for head, column in HEADS.items():
        errors = Counter()
        lengths = {"1": Counter(), "2-3": Counter(), "4+": Counter()}
        for row, tags in zip(rows, predictions[head], strict=True):
            gold, predicted = bio_spans(row[column]), bio_spans(tags)
            for start, end in gold:
                bucket = "1" if end - start == 1 else "2-3" if end - start <= 3 else "4+"
                lengths[bucket]["gold"] += 1
                lengths[bucket]["exact"] += (start, end) in predicted
                if (start, end) not in predicted:
                    overlap = any(start < right and left < end for left, right in predicted)
                    errors["missed_with_overlap" if overlap else "missed_without_overlap"] += 1
            errors["extra_predictions"] += len(predicted - gold)
        report["heads"][head] = {"errors": dict(errors), "recall_by_gold_length": {
            bucket: {**counts, "recall": round(counts["exact"] / counts["gold"], 6) if counts["gold"] else 0}
            for bucket, counts in lengths.items()}}
    report["interpretation"] = "Overlapping misses indicate possible boundary/category errors, not a manually adjudicated cause. No test-set tuning."
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["heads"], indent=2))


if __name__ == "__main__":
    main()
