from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_description: str = Field(min_length=1, max_length=50_000)
    user_skills: list[str] = Field(max_length=200)

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
