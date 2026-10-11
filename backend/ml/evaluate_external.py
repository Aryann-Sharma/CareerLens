"""Evaluate frozen extractors on Green's independently annotated test sentences."""

import argparse
import csv
import json
from pathlib import Path
from urllib.request import urlopen

import pycrfsuite

from backend.ml.contextual import collect_predictions, empty_predictions, encode_rows, pad_batch
from backend.ml.contextual_predict import load_assets as contextual_assets
from backend.ml.data import HEADS, digest, load_split, sentence_key
from backend.ml.features import bio_spans, sentence_features
from backend.ml.metrics import scores
from backend.ml.predict import load_assets as crf_assets

REVISION = "ca1eadd2885a277853b01f0ec96fc89094adf71e"
REPOSITORY = "https://github.com/acp19tag/skill-extraction-dataset"
BASE_URL = f"https://raw.githubusercontent.com/acp19tag/skill-extraction-dataset/{REVISION}"


def download(path):
    path.mkdir(parents=True, exist_ok=True)
    for name, source in (("test.csv", "preprocessed_data/df_testset.csv"), ("LICENSE", "LICENSE")):
        with urlopen(f"{BASE_URL}/{source}", timeout=60) as response:
            (path / name).write_bytes(response.read())
    manifest = {"repository": REPOSITORY, "revision": REVISION, "license": "CC-BY-4.0",
                "sha256": {name: digest(path / name) for name in ("test.csv", "LICENSE")}}
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def load_rows(path):
    groups = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for item in csv.DictReader(stream):
            row = groups.setdefault(item["sentence_id"], {"id": item["sentence_id"], "tokens": [], "gold": []})
            row["tokens"].append(item["word"])
            row["gold"].append(item["tag"].split("-")[0] if item["tag"].endswith("-Skill") else "O")
    return list(groups.values())


def measure(rows, predictions):
    tp = fp = fn = 0
    errors = []
    for index, row in enumerate(rows):
        gold = bio_spans(row["gold"])
        predicted = set().union(*(bio_spans(predictions[head][index]) for head in HEADS))
        tp += len(gold & predicted)
        fp += len(predicted - gold)
        fn += len(gold - predicted)
        if gold != predicted and len(errors) < 20:
            errors.append({"sentence_id": row["id"], "expected_spans": sorted(gold), "predicted_spans": sorted(predicted)})
    return {"overall": scores(tp, fp, fn), "error_examples": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(".data/green"))
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--model", type=Path, default=Path(".models/skillspan-distilbert"))
    parser.add_argument("--baseline", type=Path, default=Path(".models/skillspan-crf"))
    parser.add_argument("--report", type=Path, default=Path("evaluation/external-results.json"))
    args = parser.parse_args()
    if args.download:
        download(args.data)
    manifest = json.loads((args.data / "manifest.json").read_text())
    if manifest["revision"] != REVISION or any(digest(args.data / name) != value for name, value in manifest["sha256"].items()):
        raise ValueError("External data manifest/checksum mismatch")
    rows = load_rows(args.data / "test.csv")
    original = len(rows)
    seen = {sentence_key(row) for split in ("train", "dev", "test")
            for row in load_split(Path(f".data/skillspan/{split}.json"))}
    retained = []
    for row in rows:
        key = sentence_key(row)
        if key not in seen:
            retained.append(row)
            seen.add(key)
    rows = retained
    baseline, files, baseline_revision = crf_assets(args.baseline.resolve())
    predictions = empty_predictions(rows)
    for head, content in files.items():
        tagger = pycrfsuite.Tagger()
        tagger.open_inmemory(content)
        try:
            predictions[head] = [tagger.tag(sentence_features(row["tokens"], baseline["heads"][head]["config"]["window"])) for row in rows]
        finally:
            tagger.close()
    crf = measure(rows, predictions)
    model, model_revision, tokenizer, session, lock = contextual_assets(args.model.resolve())
    predictions = empty_predictions(rows)
    with lock:
        chunks = encode_rows(tokenizer, rows)
        for start in range(0, len(chunks), 8):
            batch = chunks[start:start + 8]
            arrays = pad_batch(batch)
            logits = session.run(None, {key: arrays[key] for key in ("input_ids", "attention_mask")})[0]
            collect_predictions(predictions, batch, logits)
    report = {"dataset": manifest, "original_sentences": original, "retained_sentences": len(rows),
              "duplicates_removed": original - len(rows), "usage": "evaluation only; no tuning on this corpus",
              "mapping": "Green Skill spans compared with the union of SkillSpan skill and knowledge spans; other Green entities count as outside",
              "limitations": "Different annotation policies; exact sentence deduplication does not establish posting-level independence. Supplied tokens, not raw PDF text.",
              "crf_revision": baseline_revision, "contextual_revision": model_revision,
              "crf": crf, "contextual": measure(rows, predictions)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({name: report[name]["overall"] for name in ("crf", "contextual")}, indent=2))


if __name__ == "__main__":
    main()
