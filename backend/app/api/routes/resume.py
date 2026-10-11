from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from backend.app.core.config import get_settings
from backend.app.services.pdf_worker import MAX_BYTES
from backend.app.services.resume import ResumeError, parse_pdf
from backend.app.services.skill_extractor import extract_skills
from backend.app.services.trained_extractor import ExtractorUnavailableError, extract, suggested_skills
from backend.app.api.routes.extraction import ExtractionResponse

router = APIRouter(prefix="/api", tags=["résumé"])


class ResumeResponse(BaseModel):
    text: str
    pages: int
    skills: list[str]
    extraction: ExtractionResponse | None = None
    method: Literal["trained", "catalog"]


@router.post("/resume", response_model=ResumeResponse, openapi_extra={
    "requestBody": {"required": True, "content": {"application/pdf": {
        "schema": {"type": "string", "format": "binary"},
    }}},
})
async def read_resume(request: Request, method: Literal["trained", "catalog"] = "trained") -> dict:
    """Read a PDF in memory. Return suggestions without creating a database record."""
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/pdf":
        raise HTTPException(status_code=415, detail="Upload a PDF file.")
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_BYTES:
            raise HTTPException(status_code=413, detail="Choose a PDF smaller than 5 MB.")
        content.extend(chunk)
    try:
        result = await run_in_threadpool(parse_pdf, bytes(content))
    except ResumeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    prediction = None
    if method == "trained":
        try:
            prediction = await run_in_threadpool(extract, result["text"], get_settings().extraction_model_path)
        except ExtractorUnavailableError as error:
            raise HTTPException(status_code=503, detail=(
                "Trained extraction is unavailable. Choose Catalog extraction and upload again."
            )) from error
    return {**result, "skills": suggested_skills(result["text"], prediction["spans"]) if prediction else extract_skills(result["text"]),
            "extraction": prediction, "method": method}
