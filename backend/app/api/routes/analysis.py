from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.analysis import AnalysisRequest, AnalysisResponse
from backend.app.services.analysis_store import save_analysis
from backend.app.services.scorer import analyze_skill_match
from backend.app.services.skill_extractor import extract_skills
from backend.app.services.semantic_matcher import ModelUnavailableError, analyze_semantic_match
from backend.app.core.config import get_settings
from backend.app.schemas.extraction import ExtractionDetails
from backend.app.services.trained_extractor import extract, suggested_skills, ExtractorUnavailableError
from backend.app.services.skill_extractor import canonicalize_skill

router = APIRouter(prefix="/api", tags=["analysis"])


def calculate_analysis(request: AnalysisRequest) -> AnalysisResponse:
    extracted_skills = extract_skills(request.job_description)
    extraction_details = None
    if request.reviewed_job_skills is not None:
        extracted_skills = list(dict.fromkeys(canonicalize_skill(skill) for skill in request.reviewed_job_skills))
        extraction_details = ExtractionDetails(method="reviewed")
    elif request.extraction_method == "trained":
        try:
            prediction = extract(request.job_description, get_settings().extraction_model_path)
        except ExtractorUnavailableError as error:
            raise HTTPException(status_code=503, detail=(
                "Trained extraction is unavailable. Choose Catalog extraction or try again later."
            )) from error
        extracted_skills = suggested_skills(request.job_description, prediction["spans"])
        extraction_details = ExtractionDetails(method="trained", model=prediction["model"],
                                                revision=prediction["revision"], spans=prediction["spans"])
    matching_details = None
    if request.matching_method == "semantic":
        try:
            result, matching_details = analyze_semantic_match(extracted_skills, request.user_skills)
        except ModelUnavailableError as error:
            raise HTTPException(
                status_code=503,
                detail="Semantic matching is unavailable. Choose Exact matching or try again later.",
            ) from error
    else:
        result = analyze_skill_match(extracted_skills, request.user_skills)
    return AnalysisResponse(
        extracted_skills=extracted_skills, matching_details=matching_details,
        extraction_details=extraction_details, **result,
    )


@router.post("/preview", response_model=AnalysisResponse, response_model_exclude_none=True)
def preview_job(request: AnalysisRequest) -> AnalysisResponse:
    """Compare skills without an account or any database writes."""
    return calculate_analysis(request)


@router.post("/analyze", response_model=AnalysisResponse, response_model_exclude_none=True)
def analyze_job(
    request: AnalysisRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalysisResponse:
    """Calculate and save an analysis to the signed-in user's private history."""
    analysis = calculate_analysis(request)
    record = save_analysis(
        session,
        user_id=current_user.id,
        job_description=request.job_description,
        user_skills=request.user_skills,
        extracted_skills=analysis.extracted_skills,
        result=analysis.model_dump(include={"matched_skills", "missing_skills", "match_score"}),
        matching_details=analysis.matching_details.model_dump() if analysis.matching_details else None,
        extraction_details=analysis.extraction_details.model_dump() if analysis.extraction_details else None,
    )
    response.headers["Location"] = f"/api/analyses/{record.id}"
    return analysis
