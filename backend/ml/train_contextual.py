"""Fine-tune DistilBERT on SkillSpan and export the selected checkpoint to ONNX."""

import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import random
import shutil
import time

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file, save_file
import torch
from torch import nn
from tokenizers import Tokenizer
from transformers import AutoTokenizer, DistilBertModel

from backend.ml.contextual import (
    ENCODING_VERSION, LABELS, MAX_LENGTH, STRIDE, collect_predictions,
    empty_predictions, encode_rows, pad_batch,
)
from backend.ml.data import DATA_PATH, HEADS, REVISION, clean_splits, digest, load_split
from backend.ml.metrics import evaluate, scores
from backend.ml.train import write_json

BASE_MODEL = "distilbert/distilbert-base-uncased"
BASE_REVISION = "12040accade4e8a0f71eabdb258fecc2e7e948be"


class SkillTagger(nn.Module):
    def __init__(self, source: str, **kwargs):
        super().__init__()
        self.encoder = DistilBertModel.from_pretrained(source, **kwargs)
        self.dropout = nn.Dropout(0.1)
        self.classifier = nn.Linear(self.encoder.config.dim, len(HEADS) * len(LABELS))
        nn.init.normal_(self.classifier.weight, std=0.02)
        nn.init.zeros_(self.classifier.bias)

    def forward(self, input_ids, attention_mask):
        features = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        logits = self.classifier(self.dropout(features))
        return logits.reshape(*logits.shape[:2], len(HEADS), len(LABELS))


def measure(rows, predictions):
    heads = {head: evaluate(rows, predictions[head], column) for head, column in HEADS.items()}
    counts = {key: sum(heads[head]["overall"][key] for head in HEADS) for key in ("tp", "fp", "fn")}
    return {"heads": heads, "combined": scores(**counts)}


def predict_torch(model, rows, chunks, device, batch_size=32):
    model.eval()
    predictions = empty_predictions(rows)
    with torch.inference_mode():
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            arrays = pad_batch(batch)
            logits = model(torch.from_numpy(arrays["input_ids"]).to(device),
                           torch.from_numpy(arrays["attention_mask"]).to(device))
            collect_predictions(predictions, batch, logits.cpu().numpy())
    return predictions


def run(args):
    output = args.output
    if (output / "manifest.json").exists():
        raise ValueError("Choose a new output directory; a completed model already exists here")
    output.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True, warn_only=True)
    dataset = json.loads((args.data / "manifest.json").read_text())
    if dataset["revision"] != REVISION:
        raise ValueError("Unexpected dataset revision")
    for name, expected in dataset["sha256"].items():
        if digest(args.data / name) != expected:
            raise ValueError(f"Dataset checksum mismatch: {name}")
    splits, audit = clean_splits({split: load_split(args.data / f"{split}.json")
                                for split in ("train", "dev", "test")})
    cache = Path(".models/hf-cache")
    license_path = hf_hub_download(BASE_MODEL, "LICENSE", revision=BASE_REVISION, cache_dir=cache)
    shutil.copyfile(license_path, output / "BASE-MODEL-LICENSE")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, revision=BASE_REVISION, cache_dir=cache)
    tokenizer.save_pretrained(output)
    native = Tokenizer.from_file(str(output / "tokenizer.json"))
    native.enable_truncation(max_length=MAX_LENGTH, stride=STRIDE)
    train_chunks = encode_rows(native, splits["train"])
    dev_chunks = encode_rows(native, splits["dev"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SkillTagger(BASE_MODEL, revision=BASE_REVISION, cache_dir=cache, attn_implementation="eager").to(device)
    model.encoder.config.save_pretrained(output)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    steps_per_epoch = (len(train_chunks) + args.batch_size - 1) // args.batch_size
    total_steps = steps_per_epoch * args.epochs
    warmup = max(1, total_steps // 10)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda step: (
        step / warmup if step < warmup else max(0.0, (total_steps - step) / max(1, total_steps - warmup))
    ))
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    criterion = nn.CrossEntropyLoss(ignore_index=-100)
    report = {"base_model": BASE_MODEL, "base_revision": BASE_REVISION,
              "dataset": dataset, "split_audit": audit, "encoding": ENCODING_VERSION,
              "training_chunks": len(train_chunks), "device": str(device),
              "gpu": torch.cuda.get_device_name() if device.type == "cuda" else None,
              "versions": {name: version(name) for name in ("torch", "transformers", "tokenizers", "onnxruntime")},
              "config": {"epochs": args.epochs, "seed": args.seed, "learning_rate": args.learning_rate,
                         "batch_size": args.batch_size, "max_length": MAX_LENGTH, "stride": STRIDE,
                         "weight_decay": 0.01, "warmup_steps": warmup},
              "selection": "highest development combined exact-span F1", "epochs": []}
    best_score = -1.0
    for epoch in range(1, args.epochs + 1):
        started = time.perf_counter()
        model.train()
        order = list(range(len(train_chunks)))
        random.Random(args.seed + epoch).shuffle(order)
        running_loss = 0.0
        for step, start in enumerate(range(0, len(order), args.batch_size), 1):
            batch = [train_chunks[index] for index in order[start:start + args.batch_size]]
            arrays = pad_batch(batch)
            tensors = {name: torch.from_numpy(value).to(device) for name, value in arrays.items()}
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
                logits = model(tensors["input_ids"], tensors["attention_mask"])
                loss = sum(criterion(logits[:, :, head].reshape(-1, 3), tensors["labels"][:, :, head].reshape(-1))
                           for head in range(len(HEADS))) / len(HEADS)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            running_loss += float(loss.detach())
            if step % 50 == 0:
                print(f"Epoch {epoch}/{args.epochs}, batch {step}/{steps_per_epoch}, loss {running_loss / step:.4f}", flush=True)
        metrics = measure(splits["dev"], predict_torch(model, splits["dev"], dev_chunks, device))
        result = {"epoch": epoch, "loss": running_loss / steps_per_epoch,
                  "seconds": round(time.perf_counter() - started, 3), "development": metrics}
        report["epochs"].append(result)
        if metrics["combined"]["f1"] > best_score:
            best_score = metrics["combined"]["f1"]
            report["selected_epoch"] = epoch
            save_file({name: tensor.detach().cpu().contiguous() for name, tensor in model.state_dict().items()},
                      str(output / "model.safetensors"))
        write_json(output / "training-selection.json", report)
        print(f"Epoch {epoch} development: {metrics['combined']}", flush=True)

    model.load_state_dict(load_file(str(output / "model.safetensors")))
    model = model.cpu().eval()
    sample = pad_batch(dev_chunks[:2])
    torch.onnx.export(model, (torch.from_numpy(sample["input_ids"]), torch.from_numpy(sample["attention_mask"])),
                      str(output / "model.onnx"), input_names=["input_ids", "attention_mask"], output_names=["logits"],
                      dynamic_axes={"input_ids": {0: "batch", 1: "sequence"}, "attention_mask": {0: "batch", 1: "sequence"},
                                    "logits": {0: "batch", 1: "sequence"}}, opset_version=17, dynamo=False)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    session = ort.InferenceSession(str(output / "model.onnx"), options, providers=["CPUExecutionProvider"])
    with torch.inference_mode():
        expected = model(torch.from_numpy(sample["input_ids"]), torch.from_numpy(sample["attention_mask"])).numpy()
    actual = session.run(None, {key: sample[key] for key in ("input_ids", "attention_mask")})[0]
    np.testing.assert_allclose(actual, expected, rtol=1e-3, atol=1e-4)
    manifest = {"format_version": 2, "model": "skillspan-distilbert-v1", "encoding": ENCODING_VERSION,
                "base_model": BASE_MODEL, "base_revision": BASE_REVISION, "dataset_revision": REVISION,
                "heads": list(HEADS), "labels": LABELS, "selected_epoch": report["selected_epoch"],
                "max_length": MAX_LENGTH, "stride": STRIDE,
                "sha256": {name: digest(output / name) for name in ("model.onnx", "tokenizer.json")}}
    # Freeze the exported artifact and checkpoint selection before scoring the test split.
    write_json(output / "manifest.json", manifest)
    shutil.copyfile(args.data / "LICENSE", output / "SKILLSPAN-LICENSE")
    test_chunks = encode_rows(native, splits["test"])
    predictions = empty_predictions(splits["test"])
    started = time.perf_counter()
    for start in range(0, len(test_chunks), 32):
        batch = test_chunks[start:start + 32]
        arrays = pad_batch(batch)
        logits = session.run(None, {key: arrays[key] for key in ("input_ids", "attention_mask")})[0]
        collect_predictions(predictions, batch, logits)
    report["test"] = measure(splits["test"], predictions)
    report["test_cpu_seconds"] = round(time.perf_counter() - started, 3)
    report["export_max_absolute_error"] = float(np.abs(actual - expected).max())
    report["model"] = manifest
    write_json(args.report, report)
    print(f"Selected epoch {report['selected_epoch']}; ONNX test: {report['test']['combined']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--output", type=Path, default=Path(".models/skillspan-distilbert"))
    parser.add_argument("--report", type=Path, default=Path("evaluation/contextual-results.json"))
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
