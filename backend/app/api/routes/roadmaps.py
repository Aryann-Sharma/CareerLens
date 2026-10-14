from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.api.routes.learning import PlanRequest
from backend.app.db.session import get_db
from backend.app.models import SavedRoadmap, User
from backend.app.services.learning import build_plan

CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]
RoadmapId = Annotated[int, Path(ge=1, le=2_147_483_647)]
Milestone = Annotated[str, StringConstraints(pattern=r"^\d{1,3}:\d{1,2}$", max_length=6)]


def check_account(user: CurrentUser, x_account_id: Annotated[int | None, Header()] = None):
    if x_account_id is not None and user.id != x_account_id:
        raise HTTPException(409, {"code": "account_changed", "message": "Your account changed. Sign in again."})


router = APIRouter(prefix="/api/learning/saved", tags=["saved roadmaps"], dependencies=[Depends(check_account)])


class Progress(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=100)
    completed: list[Milestone] = Field(default_factory=list, max_length=654)

    @field_validator("completed")
    @classmethod
    def unique_milestones(cls, value):
        return sorted(set(value))


class CreateRoadmap(Progress):
    client_id: UUID
    request: PlanRequest
    plan_revision: str = Field(pattern=r"^[a-f0-9]{16}$")


class UpdateRoadmap(Progress):
    version: int = Field(ge=1, le=2_147_483_646, strict=True)


def require_roadmap(session: Session, user: User, roadmap_id: int) -> SavedRoadmap:
    record = session.scalar(select(SavedRoadmap).where(SavedRoadmap.id == roadmap_id, SavedRoadmap.user_id == user.id))
    if record is None:
        raise HTTPException(404, "Saved roadmap not found.")
    return record


def validate_progress(plan: dict, completed: list[str]):
    valid = {f"{i}:{j}" for i, step in enumerate(plan["steps"]) for j in range(len(step["milestones"]))}
    if not set(completed) <= valid:
        raise HTTPException(422, "Checked steps must belong to this roadmap.")


def metadata(record: SavedRoadmap) -> dict:
    def utc(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return {"id": record.id, "title": record.title, "version": record.version,
            "completed_count": len(record.completed),
            "total_count": sum(len(step["milestones"]) for step in record.plan["steps"]),
            "created_at": utc(record.created_at), "updated_at": utc(record.updated_at)}


def detail(record: SavedRoadmap) -> dict:
    return {**metadata(record), "plan": record.plan, "completed": record.completed}


@router.get("")
def list_roadmaps(user: CurrentUser, session: Database, response: Response,
                  page: Annotated[int, Query(ge=1, le=2_147_483_647)] = 1,
                  page_size: Annotated[int, Query(ge=1, le=50)] = 10) -> dict:
    response.headers["Cache-Control"] = "no-store"
    total = session.scalar(select(func.count()).select_from(SavedRoadmap).where(SavedRoadmap.user_id == user.id))
    rows = session.scalars(select(SavedRoadmap).where(SavedRoadmap.user_id == user.id)
                           .order_by(SavedRoadmap.updated_at.desc(), SavedRoadmap.id.desc())
                           .offset((page - 1) * page_size).limit(page_size))
    return {"items": [metadata(row) for row in rows], "page": page, "page_size": page_size, "total": total}


@router.post("", status_code=201)
def create_roadmap(request: CreateRoadmap, user: CurrentUser, session: Database, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    lookup = select(SavedRoadmap).where(SavedRoadmap.user_id == user.id, SavedRoadmap.client_id == str(request.client_id))
    record = session.scalar(lookup)
    if record is not None:
        response.status_code = 200
        return detail(record)
    source = request.request
    plan = build_plan(source.missing_skills, source.user_skills, source.direction)
    if request.plan_revision != plan["revision"]:
        raise HTTPException(409, "The learning steps have changed. Download your current checklist, then rebuild the roadmap before saving.")
    validate_progress(plan, request.completed)
    record = SavedRoadmap(user_id=user.id, client_id=str(request.client_id), title=request.title,
                          plan=plan, completed=request.completed, version=1)
    session.add(record)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        record = session.scalar(lookup)
        if record is None:
            raise HTTPException(409, "The roadmap could not be saved. Please retry.")
        response.status_code = 200
    response.headers["Location"] = f"/api/learning/saved/{record.id}"
    return detail(record)


@router.get("/{roadmap_id}")
def get_roadmap(roadmap_id: RoadmapId, user: CurrentUser, session: Database, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return detail(require_roadmap(session, user, roadmap_id))


@router.put("/{roadmap_id}")
def update_roadmap(roadmap_id: RoadmapId, request: UpdateRoadmap, user: CurrentUser, session: Database, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    record = require_roadmap(session, user, roadmap_id)
    validate_progress(record.plan, request.completed)
    changed = session.execute(update(SavedRoadmap).where(SavedRoadmap.id == roadmap_id,
        SavedRoadmap.user_id == user.id, SavedRoadmap.version == request.version).values(
        title=request.title, completed=request.completed, version=request.version + 1,
        updated_at=datetime.now(timezone.utc)), execution_options={"synchronize_session": False})
    if changed.rowcount != 1:
        session.rollback()
        raise HTTPException(409, "This roadmap changed in another tab. Reopen it from Saved roadmaps before saving again.")
    session.commit()
    session.refresh(record)
    return detail(record)


@router.delete("/{roadmap_id}", status_code=204)
def delete_roadmap(roadmap_id: RoadmapId, user: CurrentUser, session: Database,
                   version: Annotated[int, Query(ge=1, le=2_147_483_647)]) -> Response:
    require_roadmap(session, user, roadmap_id)
    changed = session.execute(delete(SavedRoadmap).where(SavedRoadmap.id == roadmap_id,
        SavedRoadmap.user_id == user.id, SavedRoadmap.version == version))
    if changed.rowcount != 1:
        session.rollback()
        raise HTTPException(409, "This roadmap changed. Refresh the saved list before deleting it.")
    session.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
