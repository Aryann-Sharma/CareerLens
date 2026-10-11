from typing import Literal

from pydantic import BaseModel, Field


class SemanticMatch(BaseModel):
    skill: str
    user_skill: str
    similarity: float = Field(ge=-1, le=1)


class MatchingDetails(BaseModel):
    method: Literal["semantic"]
    model: str
    revision: str
    threshold: float
    margin: float
    exact_match_score: int = Field(ge=0, le=100)
    semantic_matches: list[SemanticMatch]
