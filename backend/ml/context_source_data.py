"""Build a source-backed context experiment with occupation-separated tasks."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
from urllib.request import urlopen

from backend.ml.context_data import load_cases

URL = "https://www.onetcenter.org/dl_files/database/db_31_0_csv/tasks_to_dwas.csv"
SHA256 = "15624d31acb85627736a87dc7c485edffe30361262571c8242fad4ae9e7678a6"

# This is a project crosswalk, not an official annotation of our capabilities.
# Select narrow activities; an unmapped task is unknown, not a negative example.
ACTIVITIES = {
    "4.A.3.b.1.a.3": ["Programming"],
    "4.A.2.b.2.b.1": ["Programming"],
    "4.A.2.b.2.b.6": ["Programming"],
    "4.A.3.b.1.d.3": ["Debugging"],
    "4.A.1.b.2.h.3": ["Software testing"],
    "4.A.2.a.4.b.5": ["Data analysis"],
    "4.A.2.a.4.d.2": ["Data analysis"],
    "4.A.2.a.4.k.4": ["Data analysis"],
    "4.A.3.b.6.p.3": ["Marketing communication", "Written communication"],
    "4.A.4.a.3.c.2": ["Presentation"],
    "4.A.4.a.6.c.7": ["Presentation", "Marketing communication"],
    "4.A.4.a.8.c.1": ["Customer support"],
    "4.A.4.a.8.c.2": ["Customer support"],
    "4.A.4.a.8.c.3": ["Customer support"],
    "4.A.4.a.8.c.5": ["Customer support"],
    "4.A.4.a.8.c.6": ["Customer support", "Written communication"],
    "4.A.3.b.6.l.5": ["Written communication"],
    "4.A.4.a.7.a.1": ["Conflict resolution"],
    "4.A.4.a.7.a.2": ["Conflict resolution"],
    "4.A.4.a.7.a.3": ["Conflict resolution"],
    "4.A.4.b.1.a.3": ["Teamwork"],
    "4.A.4.b.1.a.5": ["Teamwork"],
    "4.A.4.b.1.c.3": ["Teamwork"],
    "4.A.2.a.2.a.1": ["Attention to detail"],
    "4.A.2.a.2.a.7": ["Attention to detail"],
    "4.A.2.a.3.a.8": ["Attention to detail"],
    "4.A.4.b.3.d.1": ["Teaching"],
    "4.A.4.b.3.d.15": ["Teaching"],
    "4.A.4.b.3.e.4": ["Teaching"],
    "4.A.4.b.3.e.5": ["Teaching"],
    "4.A.4.a.7.b.1": ["Negotiation"],
    "4.A.4.a.7.b.10": ["Negotiation"],
    "4.A.4.a.7.b.7": ["Negotiation"],
    "4.A.1.a.1.t.4": ["Research"],
    "4.A.1.a.1.t.8": ["Research"],
    "4.A.1.a.1.h.2": ["Research"],
    "4.A.1.a.1.r.2": ["Research"],
}


def normalized(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def occupation_split(code):
    bucket = int(hashlib.sha256(("context-occupation-v2:" + code).encode()).hexdigest()[:8], 16) % 10
    return "train" if bucket < 7 else "dev" if bucket < 9 else "test"


def source_rows(path, download=False):
    if not path.exists() and download:
        content = urlopen(URL, timeout=60).read(20_000_001)
        if hashlib.sha256(content).hexdigest() != SHA256:
            raise ValueError("Unexpected O*NET source checksum")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise ValueError("Unexpected O*NET source checksum")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def task_cases(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[normalized(row["Task"])].append(row)
    selected, crossed = [], 0
    for key, group in sorted(groups.items()):
        labels = sorted({label for row in group for label in ACTIVITIES.get(row["DWA Element ID"], [])})
        if not labels:
            continue
        splits = {occupation_split(row["O*NET-SOC Code"]) for row in group}
        if len(splits) != 1:
            crossed += 1
            continue
        chosen = min(group, key=lambda row: (row["Task ID"], row["Task"]))
        selected.append({"id": "onet-" + hashlib.sha256(key.encode()).hexdigest()[:16],
            "family": "onet-task-" + key, "split": splits.pop(), "text": chosen["Task"],
            "expected": labels, "acceptable": [], "origin": "onet-activity-crosswalk",
            "source_id": "onet31-tasks", "group": "occupational-duty",
            "task_ids": sorted({row["Task ID"] for row in group}),
            "occupations": sorted({row["O*NET-SOC Code"] for row in group}),
            "activities": sorted({row["DWA Element ID"] for row in group})})
    # Remove near duplicates across splits too. This is conservative token-set
    # similarity, not a guarantee that every semantic paraphrase is distinct.
    tokens = [set(normalized(row["text"]).split()) for row in selected]
    excluded = set()
    for i, left in enumerate(selected):
        for j in range(i):
            if left["split"] == selected[j]["split"]:
                continue
            if len(tokens[i] & tokens[j]) / max(len(tokens[i] | tokens[j]), 1) >= .8:
                excluded.update((i, j))
    return [row for i, row in enumerate(selected) if i not in excluded], {
        "cross_split_duplicate_groups_removed": crossed,
        "cross_split_near_duplicate_rows_removed": len(excluded)}


def build(source, supplements, output, download=False, label_audit=Path("evaluation/context-source-label-audit.json")):
    rows = source_rows(source, download)
    tasks, audit = task_cases(rows)
    corrections = json.loads(label_audit.read_text(encoding="utf-8"))["changes"]
    if not set(corrections) <= {r["id"] for r in tasks}:
        raise ValueError("Label audit refers to an unknown source task")
    reviewed = []
    for task in tasks:
        change = corrections.get(task["id"])
        if change and change.get("exclude"):
            continue
        if change:
            task = {**task, "crosswalk_labels": task["expected"],
                "expected": change["expected"], "acceptable": change["acceptable"],
                "annotation_note": change["reason"]}
        reviewed.append(task)
    audit["label_audit_sha256"] = hashlib.sha256(label_audit.read_text(encoding="utf-8").encode()).hexdigest()
    audit["audited_changes"] = len(corrections)
    audit["audited_exclusions"] = len(tasks) - len(reviewed)
    tasks = reviewed
    old = load_cases(Path("evaluation/context-training-cases.json"))
    extra = json.loads(supplements.read_text(encoding="utf-8"))
    cases = [row for row in old if row["split"] != "test"] + tasks + extra["cases"]
    data = {"description": "Occupation-separated source tasks plus project-authored examples. Activity crosswalk labels are weak supervision, not independent expert annotations.",
        "label_policy": "Unmapped tasks are excluded, not treated as negative. Labels are limited to 24 capabilities and may be incomplete. Public-source paraphrases are test-only. Previous test sets remain regressions.",
        "sources": [{"id": "onet31-tasks", "url": URL, "sha256": SHA256, "accessed": "2026-10-13",
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "attribution": "O*NET 31.0 Database, U.S. Department of Labor, Employment and Training Administration. CareerLens maps selected activities to its own capabilities and adds spelling variants. These modifications are not approved, endorsed or tested by USDOL/ETA. O*NET is a trademark of USDOL/ETA."}] + extra["sources"],
        "activity_crosswalk": {key: {"name": next(r["DWA Element Name"] for r in rows if r["DWA Element ID"] == key), "labels": value} for key,value in ACTIVITIES.items()},
        "audit": {**audit, "source_task_counts": dict(Counter(row["split"] for row in tasks))},
        "cases": cases}
    output.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    load_cases(output)
    print({"counts": dict(Counter(row["split"] for row in cases)), **data["audit"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(".data/onet-31.0/tasks_to_dwas.csv"))
    parser.add_argument("--supplements", type=Path, default=Path("evaluation/context-source-supplements.json"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/context-source-cases.json"))
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    build(args.source, args.supplements, args.output, args.download)
