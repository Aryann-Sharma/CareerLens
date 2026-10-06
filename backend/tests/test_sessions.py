from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.app.core.config import get_settings
from backend.app.services.sessions import create_session_token, read_session_token


def test_session_token_round_trip() -> None:
    token = create_session_token(42)

    assert read_session_token(token) == 42


def test_expired_session_token_is_rejected() -> None:
    token = create_session_token(42, expires_delta=timedelta(seconds=-1))

    assert read_session_token(token) is None


def test_invalid_session_tokens_are_rejected() -> None:
    assert read_session_token("not-a-token") is None
    assert read_session_token("") is None


@pytest.mark.parametrize("claim", ["sub", "type", "iat", "exp"])
def test_session_requires_every_claim(claim: str) -> None:
    now = datetime.now(timezone.utc)
    payload = {"sub": "42", "type": "session", "iat": now, "exp": now + timedelta(hours=1)}
    del payload[claim]
    token = jwt.encode(payload, get_settings().auth_secret_key, algorithm="HS256")
    assert read_session_token(token) is None


@pytest.mark.parametrize(
    "overrides",
    [{"sub": "0"}, {"sub": "-1"}, {"sub": "abc"}, {"type": "access"}],
)
def test_session_rejects_invalid_identity_or_type(overrides: dict[str, str]) -> None:
    now = datetime.now(timezone.utc)
    payload = {"sub": "42", "type": "session", "iat": now, "exp": now + timedelta(hours=1)}
    payload.update(overrides)
    token = jwt.encode(payload, get_settings().auth_secret_key, algorithm="HS256")
    assert read_session_token(token) is None


def test_session_rejects_a_different_signing_algorithm() -> None:
    now = datetime.now(timezone.utc)
    payload = {"sub": "42", "type": "session", "iat": now, "exp": now + timedelta(hours=1)}
    token = jwt.encode(payload, "x" * 64, algorithm="HS512")
    assert read_session_token(token) is None
