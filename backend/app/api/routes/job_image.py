from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from backend.app.services.image_worker import MAX_BYTES
from backend.app.services.job_image import ImageReadError, read_job_image
from backend.app.schemas.job_document import JobDocumentResponse
from backend.app.services.job_document import prepare_job_document

router = APIRouter(prefix="/api", tags=["job description"])


@router.post("/job-image", response_model=JobDocumentResponse, openapi_extra={
    "requestBody": {"required": True, "content": {
        media: {"schema": {"type": "string", "format": "binary"}}
        for media in ("image/png", "image/jpeg", "image/webp")
    }},
})
async def import_job_image(request: Request, response: Response) -> dict:
    """Return editable text without saving the image or creating an analysis."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, "Choose a PNG, JPEG, or WebP image.")
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "Choose an image no larger than 5 MB.")
        content.extend(chunk)
    try:
        result = await run_in_threadpool(read_job_image, bytes(content))
    except ImageReadError as error:
        raise HTTPException(error.status_code, str(error)) from error
    response.headers["Cache-Control"] = "no-store"
    return prepare_job_document(result["text"])
