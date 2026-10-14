"""Portable character-feature role classifier; inference uses only NumPy."""

from collections import Counter
from functools import lru_cache
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import unicodedata

import numpy as np

FEATURE_SIZE = 8192
FEATURE_VERSION = "word-char-3-5-v1"
LABELS = ["data", "database", "infrastructure", "software", "web", "other"]
ROLE_CODES = {
    "data": ["15-2051.00"],
    "database": ["15-1242.00", "15-1243.00"],
    "infrastructure": ["15-1244.00"],
    "software": ["15-1251.00", "15-1252.00"],
    "web": ["15-1254.00", "15-1255.00"],
}


def normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", text).casefold()))


@lru_cache(maxsize=32768)
def feature_index(value: str) -> int:
    return int.from_bytes(hashlib.blake2s(value.encode(), digest_size=4).digest(), "little") % FEATURE_SIZE


def features(text: str) -> np.ndarray:
    words = normalized(text[:8000]).split()
    counts = Counter()
    for word in words:
        counts[feature_index("w:" + word)] += 2
        padded = "^" + word + "$"
        for size in (3, 4, 5):
            for start in range(len(padded) - size + 1):
                counts[feature_index(padded[start:start + size])] += 1
    vector = np.zeros(FEATURE_SIZE, dtype=np.float32)
    for index, count in counts.items():
        vector[index] = 1 + np.log(count)
    norm = np.linalg.norm(vector)
    return vector / norm if norm else vector


def probabilities(matrix: np.ndarray, weights: np.ndarray, bias: np.ndarray) -> np.ndarray:
    scores = matrix @ weights.T + bias
    scores -= scores.max(axis=-1, keepdims=True)
    exponent = np.exp(scores)
    return exponent / exponent.sum(axis=-1, keepdims=True)


@lru_cache(maxsize=2)
def load_model(path: str):
    root = Path(path)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest["features"] != FEATURE_VERSION or manifest["labels"] != LABELS:
        raise ValueError("Unsupported role model")
    if any(not isinstance(manifest[key], (int, float)) or not 0 <= manifest[key] <= 1
           for key in ("threshold", "margin")):
        raise ValueError("Invalid role acceptance gate")
    content = (root / "weights.npz").read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest["sha256"]:
        raise ValueError("Role weights failed verification")
    with np.load(BytesIO(content), allow_pickle=False) as archive:
        weights, bias = archive["weights"], archive["bias"]
    if weights.shape != (len(LABELS), FEATURE_SIZE) or bias.shape != (len(LABELS),):
        raise ValueError("Unexpected role weight dimensions")
    if not np.isfinite(weights).all() or not np.isfinite(bias).all():
        raise ValueError("Invalid role weights")
    return weights, bias, manifest


def suggest_role(text: str, path: Path) -> dict:
    try:
        weights, bias, manifest = load_model(str(path.resolve()))
        vector = features(text)
        if not vector.any():
            return {"status": "uncertain", "role_id": None}
        scores = probabilities(vector[None, :], weights, bias)[0]
        ranked = np.argsort(scores)[::-1]
        best, runner = ranked[:2]
        accepted = LABELS[best] != "other" and scores[best] >= manifest["threshold"] and scores[best] - scores[runner] >= manifest["margin"]
        return {"status": "suggested" if accepted else "uncertain", "role_id": LABELS[best] if accepted else None,
                "model_revision": manifest["revision"]}
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "unavailable", "role_id": None}
