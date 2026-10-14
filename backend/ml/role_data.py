"""Download and audit a pinned occupation-labelled public release."""

import argparse
from collections import defaultdict
import csv
import hashlib
from pathlib import Path
from urllib.request import urlopen

from backend.ml.role_model import ROLE_CODES, normalized

SOURCE = "https://www.onetcenter.org/dl_files/database/db_31_0_csv/"
FILES = {
    "occupation_data.csv": "a09eae1d6609686e44e05b7290993a1c8b523d8ca224bc0eedc194c855c3ee02",
    "job_titles.csv": "75a3b46d6edc5996117c10c9ed488c9a06f7495d02969e9d12873ab14a21540c",
    "task_statements.csv": "4568e14d8db6f05551ad37e056e909b13ebae4a26bcb5ff915bb5f281d582c57",
    "software_skills.csv": "6aabb96b464288db849580e6510530efff3f80e25dde2bb23f1fc36bb526b016",
}


def download(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    for name, digest in FILES.items():
        path = root / name
        content = path.read_bytes() if path.exists() else urlopen(SOURCE + name, timeout=60).read(20_000_001)
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f"Source checksum mismatch: {name}")
        if not path.exists():
            path.write_bytes(content)
        print(f"Verified {name}", flush=True)


def read_rows(root: Path, name: str) -> list[dict]:
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != FILES[name]:
        raise ValueError(f"Source checksum mismatch: {name}")
    with (root / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def dataset(root: Path) -> tuple[dict, dict]:
    groups = defaultdict(list)
    codes = {code: label for label, values in ROLE_CODES.items() for code in values}
    for filename, fields in [("job_titles.csv", ["Job Title"]), ("task_statements.csv", ["Task"]),
                             ("occupation_data.csv", ["Title", "Description"])]:
        for row in read_rows(root, filename):
            code = row["O*NET-SOC Code"]
            for field in fields:
                text = row[field].strip()
                # Ignore spacing/punctuation/case variants when splitting data.
                key = normalized(text).replace(" ", "")
                if key:
                    groups[key].append({"text": text, "label": codes.get(code, "other"), "code": code,
                                        "kind": field, "group": key})
    splits = {"train": [], "dev": [], "test": []}
    conflicts = 0
    for key, rows in groups.items():
        if len({row["label"] for row in rows}) != 1:
            conflicts += 1
            continue
        row = sorted(rows, key=lambda r: (r["kind"], r["code"], r["text"]))[0]
        digest = hashlib.sha256(("role-split-v1:" + key).encode()).hexdigest()
        bucket = int(digest[:8], 16) % 10
        split = "train" if bucket < 7 else "dev" if bucket < 9 else "test"
        # Sample negatives reproducibly, retaining adjacent computing occupations.
        if row["label"] == "other" and not row["code"].startswith("15-") and int(digest[8:16], 16) % 20:
            continue
        splits[split].append(row)
    for rows in splits.values():
        rows.sort(key=lambda row: row["group"])
    return splits, {"conflicting_groups_removed": conflicts, "normalized_groups": len(groups),
                    "duplicates_removed": sum(len(rows) - 1 for rows in groups.values()),
                    "split_policy": "SHA256 group split 70/20/10; 1 in 20 other examples, all adjacent computing examples retained"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".data/onet-31.0"))
    download(parser.parse_args().output)
