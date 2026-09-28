from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.analysis import AnalysisRecord
from backend.app.services.scorer import MatchResult


def save_analysis(
    session: Session,
    *,
    job_description: str,
    user_skills: list[str],
    extracted_skills: list[str],
    result: MatchResult,
) -> AnalysisRecord:
    record = AnalysisRecord(
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
    page: int,
    page_size: int,
) -> tuple[list[AnalysisRecord], int]:
    total = session.scalar(select(func.count()).select_from(AnalysisRecord)) or 0
    statement = (
        select(AnalysisRecord)
        .order_by(AnalysisRecord.created_at.desc(), AnalysisRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = list(session.scalars(statement).all())
    return records, total


def get_analysis(session: Session, analysis_id: int) -> AnalysisRecord | None:
    return session.get(AnalysisRecord, analysis_id)
