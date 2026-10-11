"""Parse an upload in a short-lived process and suggest skills for review."""

import json
from pathlib import Path
import subprocess
import sys

from backend.app.services.pdf_worker import MAX_BYTES


class ResumeError(ValueError):
    pass


def parse_pdf(content: bytes) -> dict:
    if len(content) > MAX_BYTES:
        raise ResumeError("Choose a PDF smaller than 5 MB.")
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "backend.app.services.pdf_worker"],
            input=content, capture_output=True, timeout=12,
            cwd=Path(__file__).resolve().parents[3],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if completed.returncode != 0:
            raise ResumeError("This PDF could not be read. Try exporting it again.")
        result = json.loads(completed.stdout)
        if "error" in result:
            raise ResumeError(result["error"])
        return result
    except subprocess.TimeoutExpired as error:
        raise ResumeError("This PDF took too long to read. Try a simpler text-based PDF.") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ResumeError("PDF extraction is unavailable. You can still enter your skills manually.") from error
