from typing import Literal

from pydantic import BaseModel, Field


class ExtractedSpan(BaseModel):
    text: str
    label: Literal["skill", "knowledge"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class SpellingCheck(BaseModel):
    original: str
    candidates: list[str]
    applied: bool
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class ContextSuggestion(BaseModel):
    skill: str
    evidence: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    similarity: float = Field(ge=-1, le=1)


class ExtractionDetails(BaseModel):
    method: Literal["trained", "reviewed", "catalog"]
    model: str | None = None
    revision: str | None = None
    spans: list[ExtractedSpan] = Field(default_factory=list)
    spelling: list[SpellingCheck] = Field(default_factory=list)
    context_suggestions: list[ContextSuggestion] = Field(default_factory=list)
    context_notice: str = ""
