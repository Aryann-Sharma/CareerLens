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
