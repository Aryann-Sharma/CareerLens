"""Train two CRF taggers on SkillSpan and select models using development F1."""

import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import time

import pycrfsuite

from backend.ml.data import DATA_PATH, HEADS, REVISION, clean_splits, digest, load_split
from backend.ml.features import FEATURE_VERSION, sentence_features
from backend.ml.metrics import build_lexicon, evaluate, lexicon_predict, scores

MODEL_PATH = Path(".models/skillspan-crf")
# Declared before test evaluation. The first candidate is a context ablation.
CANDIDATES = [
    {"window": 0, "c1": 0.1, "c2": 0.1},
    {"window": 2, "c1": 0.1, "c2": 0.1},
    {"window": 2, "c1": 0.1, "c2": 1.0},
]


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def predict(path: Path, rows: list[dict], window: int) -> list[list[str]]:
    tagger = pycrfsuite.Tagger()
    tagger.open(str(path))
    try:
        return [tagger.tag(sentence_features(row["tokens"], window)) for row in rows]
    finally:
        tagger.close()


def run(data: Path, output: Path, report_path: Path) -> dict:
    if (output / "manifest.json").exists():
        raise ValueError("A trained model already exists here; choose a new --output directory")
    manifest = json.loads((data / "manifest.json").read_text())
    if manifest["revision"] != REVISION:
        raise ValueError("Dataset revision differs from the pinned release")
    for filename, expected in manifest["sha256"].items():
        if digest(data / filename) != expected:
            raise ValueError(f"Dataset checksum mismatch: {filename}")
    splits, audit = clean_splits({name: load_split(data / f"{name}.json")
                                for name in ("train", "dev", "test")})
    output.mkdir(parents=True, exist_ok=True)
    report = {"dataset": manifest, "split_audit": audit,
              "features": FEATURE_VERSION, "python": platform.python_version(),
              "python_crfsuite": version("python-crfsuite"),
              "selection_metric": "development exact-span F1, independently per head",
              "max_iterations": 100, "experiments": {}, "test": {}}
    selected = {}
    for head, column in HEADS.items():
        experiments = []
        for index, config in enumerate(CANDIDATES):
            print(f"Training {head}: {config}", flush=True)
            started = time.perf_counter()
            trainer = pycrfsuite.Trainer(algorithm="lbfgs", verbose=False)
            for row in splits["train"]:
                trainer.append(sentence_features(row["tokens"], config["window"]), row[column])
            trainer.set_params({"c1": config["c1"], "c2": config["c2"],
                                "max_iterations": 100, "feature.possible_transitions": True})
            candidate = output / f"{head}-{index}.crfsuite"
            trainer.train(str(candidate))
            elapsed = time.perf_counter() - started
            development = evaluate(splits["dev"], predict(candidate, splits["dev"], config["window"]), column)
            experiments.append({"config": config, "file": candidate.name,
                                "training_seconds": round(elapsed, 3),
                                "development": development["overall"]})
            print(f"  Development: {development['overall']}", flush=True)
        best = max(experiments, key=lambda experiment: experiment["development"]["f1"])
        path = output / f"{head}.crfsuite"
        shutil.copyfile(output / best["file"], path)
        selected[head] = {"config": best["config"], "file": path.name,
                          "sha256": digest(path), "bytes": path.stat().st_size}
        report["experiments"][head] = experiments
    # Freeze both selections before computing any test prediction or score.
    model_manifest = {"format_version": 1, "features": FEATURE_VERSION,
                      "dataset_revision": REVISION, "heads": selected}
    write_json(output / "manifest.json", model_manifest)
    shutil.copyfile(data / "LICENSE", output / "SKILLSPAN-LICENSE")
    report["models"] = model_manifest
    write_json(output / "training-selection.json", report)
    for head, column in HEADS.items():
        chosen = selected[head]
        started = time.perf_counter()
        predictions = predict(output / chosen["file"], splits["test"], chosen["config"]["window"])
        inference = time.perf_counter() - started
        lexicon = build_lexicon(splits["train"], column)
        baseline = [lexicon_predict(row["tokens"], lexicon) for row in splits["test"]]
        report["test"][head] = {
            "crf": evaluate(splits["test"], predictions, column),
            "training_lexicon": evaluate(splits["test"], baseline, column),
            "lexicon_entries": len(lexicon),
            "seconds_including_load_and_features": round(inference, 3),
        }
        print(f"Test {head}: {report['test'][head]['crf']['overall']}", flush=True)
    for method in ("crf", "training_lexicon"):
        counts = {key: sum(report["test"][head][method]["overall"][key] for head in HEADS)
                  for key in ("tp", "fp", "fn")}
        report["test"].setdefault("combined", {})[method] = scores(**counts)
    write_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--output", type=Path, default=MODEL_PATH)
    parser.add_argument("--report", type=Path, default=Path("evaluation/training-results.json"))
    args = parser.parse_args()
    run(args.data, args.output, args.report)


if __name__ == "__main__":
    main()
