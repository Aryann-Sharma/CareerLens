"""Validate context labels and keep spelling variants within their source split."""

import hashlib
import json
from pathlib import Path
import re

from backend.app.services.context_suggestions import CAPABILITIES

VARIANTS = ("clean", "deletion", "transposition", "duplication", "joined", "spacing", "casing")


def perturb(text: str, kind: str, seed: str) -> str:
    if kind not in VARIANTS:
        raise ValueError("Unknown perturbation")
    if kind == "clean":
        return text
    if kind == "casing":
        return text.upper()
    # Do not change short polarity words such as 'no' and 'not'. One small
    # disturbance per description keeps the intended meaning inspectable.
    words = list(re.finditer(r"\b[A-Za-z]{7,}\b", text))
    if not words:
        words = list(re.finditer(r"\b[A-Za-z]{5,}\b", text))
    if not words:
        return text
    digest = int.from_bytes(hashlib.sha256(seed.encode()).digest()[:4], "little")
    word = words[digest % len(words)]
    value = word.group()
    middle = len(value) // 2
    if kind == "deletion":
        replacement = value[:middle] + value[middle + 1:]
    elif kind == "transposition":
        positions = [i for i in range(1, len(value) - 2) if value[i] != value[i + 1]]
        middle = positions[digest % len(positions)] if positions else middle
        replacement = value[:middle] + value[middle + 1] + value[middle] + value[middle + 2:]
    elif kind == "duplication":
        replacement = value[:middle] + value[middle] + value[middle:]
    elif kind == "spacing":
        replacement = value[:middle] + " " + value[middle:]
    else:
        gap = re.match(r" +(?=[A-Za-z]{3,}\b)", text[word.end():])
        if gap:
            return text[:word.end()] + text[word.end() + gap.end():]
        return text
    return text[:word.start()] + replacement + text[word.end():]


def load_cases(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))["cases"]
    ids, texts, families = set(), {}, {}
    for row in rows:
        if row["id"] in ids or row["split"] not in {"train", "dev", "test"}:
            raise ValueError("Duplicate identifier or invalid split")
        ids.add(row["id"])
        if not row["text"].strip() or not set(row["expected"] + row["acceptable"]) <= CAPABILITIES.keys():
            raise ValueError("Empty text or unknown label")
        normalized = " ".join(re.findall(r"\w+", row["text"].casefold()))
        for mapping, key in ((texts, normalized), (families, row["family"])):
            if mapping.setdefault(key, row["split"]) != row["split"]:
                raise ValueError("Related examples cross splits")
    return rows


def expanded(rows: list[dict]) -> list[dict]:
    result = []
    for row in rows:
        seen = set()
        for variant in VARIANTS:
            text = perturb(row["text"], variant, row["id"])
            if text in seen:
                continue
            seen.add(text)
            result.append({**row, "base_id": row["id"], "id": f'{row["id"]}:{variant}',
                           "variant": variant, "text": text})
    return result
