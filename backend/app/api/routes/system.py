from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.db.session import get_db

router = APIRouter(tags=["system"])


@router.get("/health")
@router.get("/health/live")
def liveness_check() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/health/ready")
def readiness_check(
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from error

    return {"status": "ready"}
