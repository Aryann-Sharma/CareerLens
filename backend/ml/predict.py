"""Run the trained extraction experiment on a new job description, offline."""

import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

import pycrfsuite

from backend.ml.data import HEADS
from backend.ml.features import FEATURE_VERSION, bio_spans, sentence_features

MODEL_PATH = Path(".models/skillspan-crf")
TOKEN_PATTERN = re.compile(r"<[^>\s]+>|\w+(?:[./+#'-]\w+)*[+#]*|[^\w\s]")


class ExtractorUnavailableError(RuntimeError):
    pass


@lru_cache(maxsize=2)
def load_assets(path: Path) -> tuple[dict, dict[str, bytes], str]:
    try:
        raw = (path / "manifest.json").read_bytes()
        manifest = json.loads(raw)
        if manifest["format_version"] != 1 or manifest["features"] != FEATURE_VERSION:
            raise ValueError("Unsupported trained model format")
        models = {}
        for head in HEADS:
            item = manifest["heads"][head]
            if item["file"] != f"{head}.crfsuite" or item["config"]["window"] not in {0, 2}:
                raise ValueError("Invalid trained model configuration")
            content = (path / item["file"]).read_bytes()
            if hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise ValueError("Trained model checksum mismatch")
            models[head] = content
        return manifest, models, hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ExtractorUnavailableError("The trained extraction model is not available") from error


def token_sentences(text: str) -> list[list[re.Match]]:
    """Preserve original offsets; split on sentence ends/newlines, cap chunks at 256 tokens."""
    sentences, current = [], []
    for token in TOKEN_PATTERN.finditer(text):
        if current and ("\n" in text[current[-1].end():token.start()] or len(current) >= 256):
            sentences.append(current)
            current = []
        current.append(token)
        if token.group() in {".", "!", "?", ";"}:
            sentences.append(current)
            current = []
    if current:
        sentences.append(current)
    return sentences


def extract(text: str, model_path: Path = MODEL_PATH) -> dict:
    if not text.strip() or len(text) > 50_000:
        raise ValueError("Enter between 1 and 50,000 characters")
    manifest, models, revision = load_assets(model_path.resolve())
    sentences = token_sentences(text)
    spans = []
    # Taggers have mutable inference state; create one per request, never share them.
    for head, content in models.items():
        tagger = pycrfsuite.Tagger()
        try:
            tagger.open_inmemory(content)
            for sentence in sentences:
                tokens = [token.group() for token in sentence]
                tags = tagger.tag(sentence_features(tokens, manifest["heads"][head]["config"]["window"]))
                for start, end in sorted(bio_spans(tags)):
                    left, right = sentence[start].start(), sentence[end - 1].end()
                    spans.append({"text": text[left:right], "label": head,
                                  "start": left, "end": right})
        except Exception as error:
            raise ExtractorUnavailableError("The trained extraction model could not run") from error
        finally:
            tagger.close()
    return {"model": "skillspan-crf-v1", "revision": revision, "experimental": True,
            "spans": sorted(spans, key=lambda span: (span["start"], span["end"], span["label"]))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="A job description of up to 10,000 characters")
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    args = parser.parse_args()
    print(json.dumps(extract(args.text, args.model), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
