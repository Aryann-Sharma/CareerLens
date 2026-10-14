"""Read an image and recognize text in an isolated process, without saving it."""

from contextlib import redirect_stdout
from io import BytesIO
import json
import re
import sys
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 12_000_000
MAX_SIDE = 8000
MAX_TEXT = 50_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
JOINED_WORDS = re.compile(r"[A-Za-z]{30,}")


def read_rows(rows) -> str:
    return "\n".join(str(row[1]).strip() for row in (rows or []) if str(row[1]).strip())


def restore_spacing(original: str, retry: str) -> str:
    """Accept a spacing retry only when every non-whitespace character agrees."""
    if (re.sub(r"\s", "", original) == re.sub(r"\s", "", retry)
            and len(JOINED_WORDS.findall(retry)) < len(JOINED_WORDS.findall(original))):
        return retry
    return original


def load_image(content: bytes) -> Image.Image:
    if len(content) > MAX_BYTES:
        raise ValueError("Choose an image no larger than 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError("Choose a PNG, JPEG, or WebP image.")
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Choose a still image, not an animation.")
                width, height = image.size
                if width * height > MAX_PIXELS or max(width, height) > MAX_SIDE:
                    raise ValueError("This image is too large. Use up to 12 megapixels and 8,000 pixels per side.")
                if min(width, height) < 32:
                    raise ValueError("This image is too small to read. Choose a clearer image.")
                oriented = ImageOps.exif_transpose(image)
                # Composite transparent screenshots onto white before recognition.
                rgba = oriented.convert("RGBA")
                background = Image.new("RGBA", rgba.size, "white")
                return Image.alpha_composite(background, rgba).convert("RGB")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("This image is too large. Choose an image up to 12 megapixels.") from error
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ValueError("This image could not be read. Try exporting it as PNG or JPEG.") from error


def recognize(image: Image.Image) -> str:
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1,
                      det_use_cuda=False, cls_use_cuda=False, rec_use_cuda=False,
                      max_side_len=3200, det_limit_side_len=1536, det_limit_type="max")
    rows, _ = engine(np.asarray(image)[:, :, ::-1].copy())
    text = read_rows(rows)
    if JOINED_WORDS.search(text):
        # Compression can erase spaces even when all letters are recognised.
        # A single high-contrast retry may recover them without guessing words.
        contrast = ImageOps.grayscale(image).point(lambda pixel: 0 if pixel < 150 else 255).convert("RGB")
        try:
            retry_rows, _ = engine(np.asarray(contrast)[:, :, ::-1].copy())
        except Exception:
            retry_rows = None  # Keep the successful first reading if the retry fails.
        text = restore_spacing(text, read_rows(retry_rows))
    if not text:
        raise ValueError("No readable text was found. Try a sharper image or paste the description instead.")
    if len(text) > MAX_TEXT:
        raise ValueError("This image contains too much text. Crop it to the job description and try again.")
    return text


def main() -> None:
    try:
        content = sys.stdin.buffer.read(MAX_BYTES + 1)
        image = load_image(content)
        with redirect_stdout(sys.stderr):
            text = recognize(image)
        result = {"text": text}
    except ValueError as error:
        result = {"error": str(error), "unavailable": False}
    except Exception:
        result = {"error": "Image reading is unavailable. You can still paste the job description.", "unavailable": True}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
