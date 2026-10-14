from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.analysis import AnalysisRequest
from backend.app.services.learning import DIRECTIONS, build_plan, get_guide

router = APIRouter(prefix="/api/learning", tags=["learning"])


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    missing_skills: list[str] = Field(max_length=200)
    user_skills: list[str] = Field(default_factory=list, max_length=200)
    direction: str | None = None

    @field_validator("missing_skills", "user_skills")
    @classmethod
    def clean_skills(cls, value):
        return AnalysisRequest.clean_user_skills(value)

    @field_validator("direction")
    @classmethod
    def valid_direction(cls, value):
        if value is not None and value not in DIRECTIONS:
            raise ValueError("Choose a listed learning direction")
        return value


@router.get("/directions")
def directions() -> dict:
    return DIRECTIONS


@router.get("/guide")
def skill_guide(skill: Annotated[str, Query(min_length=1, max_length=100)], response: Response) -> dict:
    if not skill.strip():
        raise HTTPException(422, "Enter a skill name")
    response.headers["Cache-Control"] = "no-store"
    return get_guide(skill.strip())


@router.post("/plan")
def learning_plan(request: PlanRequest, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return build_plan(request.missing_skills, request.user_skills, request.direction)
