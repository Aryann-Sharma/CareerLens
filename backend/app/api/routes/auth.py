from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import LoginRequest, RegistrationRequest, UserResponse
from backend.app.services.sessions import SESSION_COOKIE_NAME, create_session_token
from backend.app.services.user_store import authenticate_user, create_user

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _set_session_cookie(response: Response, user_id: int) -> None:
    settings = get_settings()
    max_age = settings.auth_token_expire_minutes * 60
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(user_id),
        max_age=max_age,
        httponly=True,
        secure=settings.environment.casefold() == "production",
        samesite="lax",
        path="/",
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegistrationRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        user = create_user(
            session,
            email=str(request.email),
            password=request.password,
        )
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from error

    _set_session_cookie(response, user.id)
    return user


@router.post("/login", response_model=UserResponse)
def login(
    request: LoginRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
) -> User:
    user = authenticate_user(
        session,
        email=str(request.email),
        password=request.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    _set_session_cookie(response, user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    settings = get_settings()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.environment.casefold() == "production",
        samesite="lax",
        path="/",
    )
    return response


@router.get("/me", response_model=UserResponse)
def current_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    return user
