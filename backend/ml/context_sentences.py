"""Sentence views for evaluating a context head before changing serving behaviour."""

import re

import numpy as np

from backend.app.services.context_suggestions import NEGATIVE
from backend.app.services.job_document import heading_kind


def sentence_units(text: str) -> list[dict]:
    """Keep coordinated duties together, with exact offsets and bounded work.

    A comma is not a sentence boundary. Negation and section exclusions remain
    conservative so a different segmentation cannot revive denied requirements.
    """
    units, offset, section = [], 0, None
    for line in text.splitlines(keepends=True):
        kind, _, _ = heading_kind(line)
        if kind:
            section = kind
        if section != "other":
            for match in re.finditer(r"[^.!?;\n]+(?:[.!?;]|$)", line):
                raw = match.group()
                value = raw.strip(" \t•-*\r\n")
                if not 4 <= len(value.split()) <= 85 or len(value) > 500 or NEGATIVE.search(value):
                    continue
                if re.search(r"\b(?:official title|job title)\s*:", value, re.I):
                    continue
                if len(value.split()) <= 6 and "/" in value:
                    continue
                start = offset + match.start() + raw.find(value)
                units.append({"text": value, "start": start, "end": start + len(value)})
        offset += len(line)
    if len(units) > 48:
        units = [units[int(i)] for i in np.linspace(0, len(units) - 1, 48)]
    return units
