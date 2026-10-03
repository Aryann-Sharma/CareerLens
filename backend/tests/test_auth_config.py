import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def test_production_requires_custom_auth_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", _env_file=None)


def test_auth_secret_must_be_at_least_32_characters() -> None:
    with pytest.raises(ValidationError):
        Settings(auth_secret_key="too-short", _env_file=None)
