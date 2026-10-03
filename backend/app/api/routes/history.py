from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.db.session import get_db
from backend.app.models.analysis import AnalysisRecord
from backend.app.models.user import User
from backend.app.schemas.history import (
    AnalysisDetailResponse,
    AnalysisHistoryItem,
    AnalysisHistoryResponse,
)
from backend.app.services.analysis_store import get_analysis, list_analyses

router = APIRouter(prefix="/api/analyses", tags=["history"])


def _description_preview(description: str, max_length: int = 180) -> str:
    single_line = " ".join(description.split())
    if len(single_line) <= max_length:
        return single_line
    return f"{single_line[: max_length - 3].rstrip()}..."


def _history_item(record: AnalysisRecord) -> AnalysisHistoryItem:
    return AnalysisHistoryItem(
        id=record.id,
        job_description_preview=_description_preview(record.job_description),
        user_skills=record.user_skills,
        matched_skills=record.matched_skills,
        missing_skills=record.missing_skills,
        match_score=record.match_score,
        created_at=record.created_at,
    )


@router.get("", response_model=AnalysisHistoryResponse)
def analysis_history(
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> AnalysisHistoryResponse:
    records, total = list_analyses(
        session,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size
    return AnalysisHistoryResponse(
        items=[_history_item(record) for record in records],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{analysis_id}", response_model=AnalysisDetailResponse)
def analysis_detail(
    analysis_id: int,
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalysisRecord:
    record = get_analysis(
        session,
        analysis_id=analysis_id,
        user_id=current_user.id,
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    return record
