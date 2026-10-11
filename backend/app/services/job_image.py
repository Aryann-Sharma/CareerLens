"""Bound image-reading work and keep uploads out of persistent storage."""

import json
from pathlib import Path
import subprocess
import sys
from threading import BoundedSemaphore

from backend.app.services.image_worker import MAX_BYTES

_slots = BoundedSemaphore(2)


class ImageReadError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def read_job_image(content: bytes) -> dict:
    if len(content) > MAX_BYTES:
        raise ImageReadError("Choose an image no larger than 5 MB.", 413)
    if not _slots.acquire(blocking=False):
        raise ImageReadError("Image reading is busy. Please try again shortly.", 503)
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "backend.app.services.image_worker"],
            input=content, capture_output=True, timeout=30,
            cwd=Path(__file__).resolve().parents[3],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if completed.returncode != 0:
            raise ImageReadError("This image could not be read. Try a smaller, clearer image.")
        result = json.loads(completed.stdout)
        if "error" in result:
            raise ImageReadError(result["error"], 503 if result.get("unavailable") else 422)
        return result
    except subprocess.TimeoutExpired as error:
        raise ImageReadError("This image took too long to read. Crop it to the job description and try again.") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ImageReadError("Image reading is unavailable. You can still paste the description.", 503) from error
    finally:
        _slots.release()
