from datetime import timedelta

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
