"""Run the fine-tuned span tagger locally using its verified ONNX export."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path
from threading import Lock

import onnxruntime as ort
from tokenizers import Tokenizer

from backend.ml.contextual import (
    ENCODING_VERSION, LABELS, MAX_LENGTH, STRIDE, collect_predictions,
    empty_predictions, encode_rows, pad_batch,
)
from backend.ml.data import HEADS, digest
from backend.ml.features import bio_spans
from backend.ml.predict import ExtractorUnavailableError, TOKEN_PATTERN, token_sentences


@lru_cache(maxsize=2)
def load_assets(path: Path):
    try:
        raw = (path / "manifest.json").read_bytes()
        manifest = json.loads(raw)
        if (manifest["format_version"] != 2 or manifest["encoding"] != ENCODING_VERSION
                or manifest["heads"] != list(HEADS) or manifest["labels"] != LABELS
                or manifest["max_length"] != MAX_LENGTH or manifest["stride"] != STRIDE):
            raise ValueError("Unsupported extraction model")
        for name in ("model.onnx", "tokenizer.json"):
            if digest(path / name) != manifest["sha256"][name]:
                raise ValueError("Extraction model checksum mismatch")
        tokenizer = Tokenizer.from_file(str(path / "tokenizer.json"))
        tokenizer.enable_truncation(max_length=MAX_LENGTH, stride=STRIDE)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        session = ort.InferenceSession(str(path / "model.onnx"), options,
                                       providers=["CPUExecutionProvider"])
        return manifest, hashlib.sha256(raw).hexdigest(), tokenizer, session, Lock()
    except Exception as error:
        raise ExtractorUnavailableError("The contextual extraction model is unavailable") from error


def extract(text: str, model_path: Path) -> dict:
    if not text.strip() or len(text) > 50_000:
        raise ValueError("Enter between 1 and 50,000 characters")
    return _extract_rows(text, token_sentences(text), model_path)


def extract_fragments(text: str, fragments: list[dict], model_path: Path) -> dict:
    """Recheck bounded fragments with skill context; synthetic words never become spans."""
    sentences = [list(TOKEN_PATTERN.finditer(text, item["start"], item["end"])) for item in fragments]
    return _extract_rows(text, sentences, model_path, prefix=["Skills", ":"])


def _extract_rows(text: str, sentences: list, model_path: Path, prefix: list[str] | None = None) -> dict:
    manifest, revision, tokenizer, session, lock = load_assets(model_path.resolve())
    prefix = prefix or []
    rows = [{"tokens": [*prefix, *(token.group() for token in sentence)]} for sentence in sentences]
    predictions = empty_predictions(rows)
    try:
        # Limit concurrent CPU/memory use and avoid sharing mutable tokenizer state.
        with lock:
            chunks = encode_rows(tokenizer, rows)
            for start in range(0, len(chunks), 8):
                batch = chunks[start:start + 8]
                arrays = pad_batch(batch)
                logits = session.run(None, {key: arrays[key] for key in ("input_ids", "attention_mask")})[0]
                collect_predictions(predictions, batch, logits)
        spans = []
        for head in HEADS:
            for sentence, tags in zip(sentences, predictions[head], strict=True):
                for start, end in sorted(bio_spans(tags)):
                    if start < len(prefix):
                        continue
                    start, end = start - len(prefix), end - len(prefix)
                    left, right = sentence[start].start(), sentence[end - 1].end()
                    spans.append({"text": text[left:right], "label": head, "start": left, "end": right})
        return {"model": manifest["model"], "revision": revision, "experimental": True,
                "spans": sorted(spans, key=lambda span: (span["start"], span["end"], span["label"]))}
    except Exception as error:
        raise ExtractorUnavailableError("The contextual extraction model could not run") from error
