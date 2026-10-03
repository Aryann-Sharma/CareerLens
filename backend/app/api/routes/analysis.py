from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.analysis import AnalysisRequest, AnalysisResponse
from backend.app.services.analysis_store import save_analysis
from backend.app.services.scorer import analyze_skill_match
from backend.app.services.skill_extractor import extract_skills

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResponse)
def analyze_job(
    request: AnalysisRequest,
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalysisResponse:
    """Extract skills from a job description and compare them with a user profile."""
    extracted_skills = extract_skills(request.job_description)
    result = analyze_skill_match(extracted_skills, request.user_skills)
    save_analysis(
        session,
        user_id=current_user.id,
        job_description=request.job_description,
        user_skills=request.user_skills,
        extracted_skills=extracted_skills,
        result=result,
    )
    return AnalysisResponse(extracted_skills=extracted_skills, **result)
