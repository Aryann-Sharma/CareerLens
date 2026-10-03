from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.analysis import AnalysisRecord
from backend.app.services.scorer import MatchResult


def save_analysis(
    session: Session,
    *,
    user_id: int,
    job_description: str,
    user_skills: list[str],
    extracted_skills: list[str],
    result: MatchResult,
) -> AnalysisRecord:
    record = AnalysisRecord(
        user_id=user_id,
        job_description=job_description,
        user_skills=list(user_skills),
        extracted_skills=list(extracted_skills),
        matched_skills=list(result["matched_skills"]),
        missing_skills=list(result["missing_skills"]),
        match_score=result["match_score"],
    )
    session.add(record)

    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(record)
    return record


def list_analyses(
    session: Session,
    *,
    user_id: int,
    page: int,
    page_size: int,
) -> tuple[list[AnalysisRecord], int]:
    owner_filter = AnalysisRecord.user_id == user_id
    total = session.scalar(
        select(func.count()).select_from(AnalysisRecord).where(owner_filter)
    ) or 0
    statement = (
        select(AnalysisRecord)
        .where(owner_filter)
        .order_by(AnalysisRecord.created_at.desc(), AnalysisRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = list(session.scalars(statement).all())
    return records, total


def get_analysis(
    session: Session,
    *,
    analysis_id: int,
    user_id: int,
) -> AnalysisRecord | None:
    return session.scalar(
        select(AnalysisRecord).where(
            AnalysisRecord.id == analysis_id,
            AnalysisRecord.user_id == user_id,
        )
    )
