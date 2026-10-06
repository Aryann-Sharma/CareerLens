import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def test_production_requires_custom_auth_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://localhost/careerlens",
            _env_file=None,
        )


def test_production_requires_postgresql() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_url="sqlite:///./careerlens.db",
            auth_secret_key="a-production-secret-that-is-long-enough",
            _env_file=None,
        )


def test_auth_secret_must_be_at_least_32_characters() -> None:
    with pytest.raises(ValidationError):
        Settings(auth_secret_key="too-short", _env_file=None)
