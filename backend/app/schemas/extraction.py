from typing import Literal

from pydantic import BaseModel, Field


class ExtractedSpan(BaseModel):
    text: str
    label: Literal["skill", "knowledge"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class ExtractionDetails(BaseModel):
    method: Literal["trained", "reviewed"]
    model: str | None = None
    revision: str | None = None
    spans: list[ExtractedSpan] = Field(default_factory=list)
