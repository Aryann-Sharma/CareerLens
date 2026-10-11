from pydantic import BaseModel, Field

from backend.app.services.pdf_worker import MAX_TEXT


class JobDocumentResponse(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT)
    full_text: str = Field(min_length=1, max_length=MAX_TEXT)
    selected_sections: list[str]
    selection_applied: bool
    pages: int | None = None
