from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from backend.app.core.config import get_settings

SESSION_COOKIE_NAME = "careerlens_session"
SESSION_ALGORITHM = "HS256"


def create_session_token(
    user_id: int,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.auth_token_expire_minutes)
    )
    payload = {
        "sub": str(user_id),
        "type": "session",
        "iat": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.auth_secret_key,
        algorithm=SESSION_ALGORITHM,
    )


def read_session_token(token: str) -> int | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[SESSION_ALGORITHM],
            options={"require": ["sub", "type", "iat", "exp"]},
        )
        if payload.get("type") != "session":
            return None
        user_id = int(payload["sub"])
    except (InvalidTokenError, TypeError, ValueError):
        return None

    return user_id if user_id > 0 else None
