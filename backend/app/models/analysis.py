from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base

skill_list_type = JSON().with_variant(JSONB(), "postgresql")


class AnalysisRecord(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint(
            "match_score >= 0 AND match_score <= 100",
            name="ck_analyses_match_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    user_skills: Mapped[list[str]] = mapped_column(skill_list_type, nullable=False)
    extracted_skills: Mapped[list[str]] = mapped_column(skill_list_type, nullable=False)
    matched_skills: Mapped[list[str]] = mapped_column(skill_list_type, nullable=False)
    missing_skills: Mapped[list[str]] = mapped_column(skill_list_type, nullable=False)
    match_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
