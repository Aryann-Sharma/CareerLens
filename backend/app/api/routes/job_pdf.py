from threading import BoundedSemaphore

from fastapi import APIRouter, HTTPException, Request, Response

from backend.app.api.pdf_upload import parse_upload, read_upload
from backend.app.schemas.job_document import JobDocumentResponse
from backend.app.services.job_document import prepare_job_document

router = APIRouter(prefix="/api", tags=["job description"])
_slots = BoundedSemaphore(2)


@router.post("/job-pdf", response_model=JobDocumentResponse, openapi_extra={
    "requestBody": {"required": True, "content": {"application/pdf": {
        "schema": {"type": "string", "format": "binary"},
    }}},
})
async def import_job_pdf(request: Request, response: Response) -> dict:
    """Return reviewable job text without storing the PDF or running skill analysis."""
    content = await read_upload(request)
    if not _slots.acquire(blocking=False):
        raise HTTPException(503, "PDF reading is busy. Please try again shortly.")
    try:
        parsed = await parse_upload(content)
    finally:
        _slots.release()
    response.headers["Cache-Control"] = "no-store"
    return {**prepare_job_document(parsed["text"]), "pages": parsed["pages"]}
