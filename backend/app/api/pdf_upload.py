"""Shared PDF upload validation for profiles and job descriptions."""

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from backend.app.services.pdf_worker import MAX_BYTES
from backend.app.services.resume import ResumeError, parse_pdf


async def read_upload(request: Request) -> bytes:
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/pdf":
        raise HTTPException(415, "Upload a PDF file.")
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "Choose a PDF smaller than 5 MB.")
        content.extend(chunk)
    return bytes(content)


async def parse_upload(content: bytes) -> dict:
    try:
        return await run_in_threadpool(parse_pdf, content)
    except ResumeError as error:
        raise HTTPException(422, str(error)) from error
