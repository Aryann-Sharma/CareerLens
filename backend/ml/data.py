"""Download and validate the public SkillSpan release."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

REVISION = "2ccf3de5b5af7a5409b8dd814fb1315dd6e0ae1b"
BASE_URL = f"https://raw.githubusercontent.com/kris927b/SkillSpan/{REVISION}"
DATA_PATH = Path(".data/skillspan")
HEADS = {"skill": "tags_skill", "knowledge": "tags_knowledge"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_split(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"Empty or invalid split: {path}")
    for row in rows:
        tokens = row["tokens"]
        if not tokens or any(not isinstance(token, str) or not token for token in tokens):
            raise ValueError("Each sentence must contain nonempty string tokens")
        if row["source"] not in {"house", "tech"}:
            raise ValueError("Unexpected data source")
        for head, column in HEADS.items():
            tags = row[column]
            valid = {"O", "B", "I"}
            if len(tokens) != len(tags) or not set(tags) <= valid:
                raise ValueError("Invalid or misaligned BIO labels")
    return rows


def sentence_key(row: dict) -> str:
    # Deliberately conservative: case and whitespace changes do not create new data.
    return " ".join(" ".join(row["tokens"]).casefold().split())


def clean_splits(splits: dict[str, list[dict]]) -> tuple[dict[str, list[dict]], dict]:
    """Keep official boundaries; remove later exact duplicates, never reassign rows.

    Posting identifiers restart per split in the source release, so they cannot
    establish cross-split independence. This check only proves sentence deduplication.
    """
    seen = set()
    cleaned, audit = {}, {}
    for name in ("train", "dev", "test"):
        kept = []
        for row in splits[name]:
            key = sentence_key(row)
            if key not in seen:
                kept.append(row)
                seen.add(key)
        cleaned[name] = kept
        audit[name] = {"original": len(splits[name]), "retained": len(kept),
                       "duplicates_removed": len(splits[name]) - len(kept)}
    return cleaned, audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DATA_PATH)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for filename in ("train.json", "dev.json", "test.json", "LICENSE"):
        relative = filename if filename == "LICENSE" else f"data/json/{filename}"
        with urlopen(f"{BASE_URL}/{relative}", timeout=60) as response:
            contents = response.read()
        path = args.output / filename
        path.write_bytes(contents)
        hashes[filename] = digest(path)
        if filename.endswith(".json"):
            print(f"{filename}: {len(load_split(path))} sentences", flush=True)
    manifest = {"repository": "https://github.com/kris927b/SkillSpan",
                "revision": REVISION, "sha256": hashes}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
