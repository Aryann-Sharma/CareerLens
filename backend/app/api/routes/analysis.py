from fastapi import APIRouter

from backend.app.schemas.analysis import AnalysisRequest, AnalysisResponse
from backend.app.services.scorer import analyze_skill_match
from backend.app.services.skill_extractor import extract_skills

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResponse)
def analyze_job(request: AnalysisRequest) -> AnalysisResponse:
    """Extract skills from a job description and compare them with a user profile."""
    extracted_skills = extract_skills(request.job_description)
    result = analyze_skill_match(extracted_skills, request.user_skills)
    return AnalysisResponse(extracted_skills=extracted_skills, **result)
