from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.matching import MatchingDetails
from backend.app.schemas.extraction import ExtractionDetails


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_description: str = Field(min_length=1, max_length=50_000)
    user_skills: list[str] = Field(max_length=200)
    matching_method: Literal["exact", "semantic"] = "exact"
    extraction_method: Literal["catalog", "trained"] = "catalog"
    reviewed_job_skills: list[str] | None = Field(default=None, max_length=200)

    @field_validator("reviewed_job_skills")
    @classmethod
    def clean_reviewed_skills(cls, skills):
        return None if skills is None else cls.clean_user_skills(skills)

    @field_validator("job_description")
    @classmethod
    def reject_blank_description(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Job description cannot be blank")
        return value.strip()

    @field_validator("user_skills")
    @classmethod
    def clean_user_skills(cls, skills: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for skill in skills:
            value = skill.strip()
            if len(value) > 100:
                raise ValueError("Each skill must be 100 characters or fewer")
            key = value.casefold()
            if value and key not in seen:
                cleaned.append(value)
                seen.add(key)
        return cleaned


class AnalysisResponse(BaseModel):
    extracted_skills: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    match_score: int = Field(ge=0, le=100)
    matching_details: MatchingDetails | None = None
    extraction_details: ExtractionDetails | None = None
