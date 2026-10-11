"""Token features shared by training and prediction; no labels are inputs."""

import re

FEATURE_VERSION = "word-context-v1"


def shape(word: str) -> str:
    raw = "".join("X" if c.isupper() else "x" if c.islower() else "d" if c.isdigit() else c
                  for c in word)
    return re.sub(r"(.)\1+", r"\1", raw)


def sentence_features(tokens: list[str], window: int = 2) -> list[dict]:
    features = []
    for index, token in enumerate(tokens):
        word = token.casefold()
        item = {"bias": 1.0, "word": word, "shape": shape(token),
                "upper": token.isupper(), "title": token.istitle(),
                "digit": token.isdigit(), "hyphen": "-" in token,
                "prefix2": word[:2], "prefix3": word[:3],
                "suffix2": word[-2:], "suffix3": word[-3:],
                "bos": index == 0, "eos": index == len(tokens) - 1}
        for offset in range(-window, window + 1):
            other = index + offset
            if offset and 0 <= other < len(tokens):
                neighbor = tokens[other]
                item[f"{offset}:word"] = neighbor.casefold()
                item[f"{offset}:shape"] = shape(neighbor)
        features.append(item)
    return features


def bio_spans(tags: list[str]) -> set[tuple[int, int]]:
    """Decode half-open spans, treating an orphan I as a new span."""
    spans, start = set(), None
    for index, tag in enumerate([*tags, "O"]):
        if tag not in {"B", "I", "O"}:
            raise ValueError(f"Invalid BIO tag: {tag}")
        if start is not None and tag != "I":
            spans.add((start, index))
            start = None
        if tag == "B" or (tag == "I" and start is None):
            start = index
    return spans
