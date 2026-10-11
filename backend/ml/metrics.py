"""Exact-boundary span metrics and a training-only dictionary baseline."""

from collections import Counter

from backend.ml.features import bio_spans


def scores(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(precision, 6), "recall": round(recall, 6),
            "f1": round(2 * tp / (2 * tp + fp + fn), 6) if 2 * tp + fp + fn else 0.0,
            "tp": tp, "fp": fp, "fn": fn, "support": tp + fn}


def evaluate(rows: list[dict], predictions: list[list[str]], column: str) -> dict:
    if len(rows) != len(predictions):
        raise ValueError("One prediction sequence is required per sentence")
    totals = Counter()
    sources = {name: Counter() for name in ("house", "tech")}
    errors = []
    for index, (row, tags) in enumerate(zip(rows, predictions)):
        if len(tags) != len(row["tokens"]):
            raise ValueError("Prediction token count differs from the input")
        gold, predicted = bio_spans(row[column]), bio_spans(tags)
        counts = {"tp": len(gold & predicted), "fp": len(predicted - gold),
                  "fn": len(gold - predicted)}
        totals.update(counts)
        sources[row["source"]].update(counts)
        if gold != predicted and len(errors) < 10:
            # Identifiers and offsets allow inspection without republishing job text.
            errors.append({"row": index, "posting": row["idx"], "source": row["source"],
                           "expected_spans": sorted(gold), "predicted_spans": sorted(predicted)})
    return {"overall": scores(totals["tp"], totals["fp"], totals["fn"]),
            "by_source": {name: scores(c["tp"], c["fp"], c["fn"]) for name, c in sources.items()},
            "error_examples": errors}


def build_lexicon(rows: list[dict], column: str) -> set[tuple[str, ...]]:
    counts = Counter(
        tuple(t.casefold() for t in row["tokens"][start:end])
        for row in rows for start, end in bio_spans(row[column])
    )
    return {phrase for phrase, count in counts.items() if count >= 2}


def lexicon_predict(tokens: list[str], lexicon: set[tuple[str, ...]]) -> list[str]:
    words = [token.casefold() for token in tokens]
    lengths = sorted({len(phrase) for phrase in lexicon}, reverse=True)
    tags, index = ["O"] * len(words), 0
    while index < len(words):
        for length in lengths:
            if index + length <= len(words) and tuple(words[index:index + length]) in lexicon:
                tags[index:index + length] = ["B", *(["I"] * (length - 1))]
                index += length
                break
        else:
            index += 1
    return tags
