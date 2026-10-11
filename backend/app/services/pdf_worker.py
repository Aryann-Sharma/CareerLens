"""Isolated, time-limited PDF text extraction. Reads stdin; never saves the PDF."""

from io import BytesIO
import json
import sys

from pypdf import PdfReader, overwrite_configuration

MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 10
MAX_TEXT = 50_000


def read_pdf(content: bytes) -> dict:
    if len(content) > MAX_BYTES or not content.startswith(b"%PDF-"):
        raise ValueError("Choose a valid PDF smaller than 5 MB.")
    overwrite_configuration(
        zlib_maximum_output_length=8 * 1024 * 1024,
        lzw_maximum_output_length=8 * 1024 * 1024,
        run_length_maximum_output_length=8 * 1024 * 1024,
        array_based_stream_maximum_output_length=8 * 1024 * 1024,
        maximum_declared_stream_length=8 * 1024 * 1024,
        page_tree_maximum_entries=1000,
    )
    reader = PdfReader(BytesIO(content))
    if reader.is_encrypted:
        raise ValueError("This PDF is password protected. Upload an unencrypted copy.")
    if not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Upload a PDF with 1 to 10 pages.")
    parts = []
    size = 0
    for page in reader.pages:
        part = page.extract_text() or ""
        size += len(part) + 1
        if size > MAX_TEXT:
            raise ValueError("The PDF contains too much text. Upload a shorter document.")
        parts.append(part)
    text = "\n".join(parts).strip()
    if not text:
        raise ValueError("No readable text found. Scanned PDFs need OCR; upload a text-based PDF.")
    return {"text": text, "pages": len(reader.pages)}


def main():
    try:
        result = read_pdf(sys.stdin.buffer.read(MAX_BYTES + 1))
    except ValueError as error:
        result = {"error": str(error)}
    except Exception:
        result = {"error": "This PDF could not be read. Try exporting it again."}
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
