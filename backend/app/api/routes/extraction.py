from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import get_settings
from backend.app.services.trained_extractor import ExtractorUnavailableError, extract
from backend.app.schemas.extraction import ExtractedSpan

router = APIRouter(prefix="/api", tags=["extraction"])


class ExtractionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    job_description: str = Field(min_length=1, max_length=50_000)


class ExtractionResponse(BaseModel):
    model: str
    revision: str
    experimental: bool
    spans: list[ExtractedSpan]


@router.post("/extract", response_model=ExtractionResponse)
def extract_job_skills(request: ExtractionRequest) -> dict:
    """Preview trained span extraction. Results do not alter or save a fit score."""
    try:
        return extract(request.job_description, get_settings().extraction_model_path)
    except ExtractorUnavailableError as error:
        raise HTTPException(status_code=503, detail=(
            "The trained extraction preview is unavailable. You can still analyze your fit."
        )) from error
