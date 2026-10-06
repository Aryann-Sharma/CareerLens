from pydantic import BaseModel, ConfigDict

from backend.app.schemas.dates import UTCDateTime


class AnalysisHistoryItem(BaseModel):
    id: int
    job_description_preview: str
    user_skills: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    match_score: int
    created_at: UTCDateTime


class AnalysisHistoryResponse(BaseModel):
    items: list[AnalysisHistoryItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class AnalysisDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_description: str
    user_skills: list[str]
    extracted_skills: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    match_score: int
    created_at: UTCDateTime
