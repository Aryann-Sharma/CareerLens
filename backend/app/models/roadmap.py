from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.models.analysis import skill_list_type


class SavedRoadmap(Base):
    __tablename__ = "saved_roadmaps"
    __table_args__ = (
        UniqueConstraint("user_id", "client_id", name="uq_saved_roadmaps_user_client"),
        CheckConstraint("version >= 1", name="ck_saved_roadmaps_version"),
        Index("ix_saved_roadmaps_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    plan: Mapped[dict] = mapped_column(skill_list_type, nullable=False)
    completed: Mapped[list[str]] = mapped_column(skill_list_type, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
