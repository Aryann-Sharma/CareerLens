from datetime import datetime, timezone
import re
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.app.core.config import get_settings
from backend.app.api.pdf_upload import parse_upload, read_upload
from backend.app.services.skill_extractor import extract_skills
from backend.app.services.trained_extractor import ExtractorUnavailableError, extract, suggested_skills, usable_skill_spans
from backend.app.api.routes.extraction import ExtractionResponse
from backend.app.api.dependencies import get_current_user
from backend.app.db.session import get_db
from backend.app.models import SavedResume, User
from backend.app.schemas.extraction import SpellingCheck
from backend.app.services.skill_spelling import correct_known_typos, spelling_checks

router = APIRouter(prefix="/api", tags=["résumé"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]


class ResumeResponse(BaseModel):
    text: str
    pages: int
    skills: list[str]
    extraction: ExtractionResponse | None = None
    method: Literal["trained", "catalog"]
    spelling: list[SpellingCheck] = Field(default_factory=list)


@router.post("/resume", response_model=ResumeResponse, openapi_extra={
    "requestBody": {"required": True, "content": {"application/pdf": {
        "schema": {"type": "string", "format": "binary"},
    }}},
})
async def read_resume(request: Request, method: Literal["trained", "catalog"] = "trained") -> dict:
    """Read a PDF in memory. Return suggestions without creating a database record."""
    content = await read_upload(request)
    result = await parse_upload(content)
    return await find_resume_skills(result, method)


async def find_resume_skills(result: dict, method: str) -> dict:
    prediction = None
    if method == "trained":
        try:
            prediction = await run_in_threadpool(extract, result["text"], get_settings().extraction_model_path)
        except ExtractorUnavailableError as error:
            raise HTTPException(status_code=503, detail=(
                "Finding skills in context is unavailable. Choose 'Find listed technical skills' and try again."
            )) from error
        prediction = {**prediction, "spans": usable_skill_spans(prediction["spans"])}
    return {**result, "skills": suggested_skills(result["text"], prediction["spans"]) if prediction else extract_skills(correct_known_typos(result["text"])),
            "extraction": prediction, "method": method, "spelling": spelling_checks(result["text"])}


class SavedResumeResponse(BaseModel):
    filename: str
    pages: int
    byte_size: int
    updated_at: datetime


def require_resume(session: Session, user: User) -> SavedResume:
    record = session.get(SavedResume, user.id)
    if record is None:
        raise HTTPException(404, "You have no saved résumé yet.")
    return record


def metadata(record: SavedResume) -> dict:
    result = {key: getattr(record, key) for key in ("filename", "pages", "byte_size", "updated_at")}
    if record.updated_at.tzinfo is None:
        result["updated_at"] = record.updated_at.replace(tzinfo=timezone.utc)
    return result


@router.get("/resume/saved", response_model=SavedResumeResponse)
def saved_resume(user: CurrentUser, session: Database, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return metadata(require_resume(session, user))


@router.put("/resume/saved", response_model=SavedResumeResponse, openapi_extra={
    "requestBody": {"required": True, "content": {"application/pdf": {
        "schema": {"type": "string", "format": "binary"},
    }}},
})
async def save_resume(request: Request, user: CurrentUser, session: Database, response: Response,
                      filename: Annotated[str, Query(max_length=255)] = "resume.pdf") -> dict:
    """Validate before replacing the account's previous PDF in one transaction."""
    content = await read_upload(request)
    parsed = await parse_upload(content)
    name = re.sub(r"[\x00-\x1f\x7f]", "", filename.replace("\\", "/").split("/")[-1]).strip()
    name = name[:196] if name else "resume"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    record = session.get(SavedResume, user.id)
    if record is None:
        record = SavedResume(user_id=user.id)
        session.add(record)
    record.filename = name
    record.pages = parsed["pages"]
    record.byte_size = len(content)
    record.content = content
    record.text = parsed["text"]
    record.updated_at = datetime.now(timezone.utc)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(409, "Your saved résumé changed. Please try saving again.") from error
    response.headers["Cache-Control"] = "no-store"
    return metadata(record)


@router.post("/resume/saved/skills", response_model=ResumeResponse)
async def reuse_resume(user: CurrentUser, session: Database, response: Response,
                       method: Literal["trained", "catalog"] = "trained") -> dict:
    record = require_resume(session, user)
    response.headers["Cache-Control"] = "no-store"
    return await find_resume_skills({"text": record.text, "pages": record.pages}, method)


@router.get("/resume/saved/file")
def download_resume(user: CurrentUser, session: Database) -> Response:
    record = require_resume(session, user)
    return Response(record.content, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=resume.pdf; filename*=UTF-8''{quote(record.filename, safe='')}",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })


@router.delete("/resume/saved", status_code=204)
def delete_resume(user: CurrentUser, session: Database) -> Response:
    session.delete(require_resume(session, user))
    session.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
