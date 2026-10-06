from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.schemas.dates import as_utc
from backend.app.services.skill_extractor import SKILL_ALIASES, extract_skills


def test_api_dates_include_utc_offset(authenticated_client: TestClient) -> None:
    client = authenticated_client
    user = client.get("/api/auth/me").json()
    client.post("/api/analyze", json={"job_description": "Python", "user_skills": []})
    item = client.get("/api/analyses").json()["items"][0]
    detail = client.get(f"/api/analyses/{item['id']}").json()
    for record in (user, item, detail):
        date = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
        assert date.utcoffset() == timedelta(0)


@pytest.mark.parametrize("table", ["analyses", "users"])
def test_readiness_rejects_missing_schema(
    client: TestClient, db_session: Session, table: str,
) -> None:
    db_session.execute(text(f"DROP TABLE {table}"))
    db_session.commit()
    assert client.get("/health/live").status_code == 200
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable or schema not ready"}


def test_utc_normalization_preserves_the_instant() -> None:
    date = datetime(2026, 10, 7, 9, tzinfo=timezone(timedelta(hours=8)))
    assert as_utc(date) == datetime(2026, 10, 7, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize("environment", [" Production ", "PRODUCTION"])
def test_production_environment_is_normalized(environment: str) -> None:
    with pytest.raises(ValidationError):
        Settings(environment=environment, _env_file=None)


def test_unknown_environment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="prodution", _env_file=None)


@pytest.mark.parametrize("url", ["postgresql-invalid://localhost/db", "postgresql://localhost/db"])
def test_production_requires_the_installed_database_driver(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", database_url=url, auth_secret_key="x" * 64, _env_file=None)


@pytest.mark.parametrize("canonical,aliases", SKILL_ALIASES.items())
def test_all_aliases_extract_only_their_own_skill(canonical: str, aliases: tuple[str, ...]) -> None:
    for alias in aliases:
        assert extract_skills(f"Required: {alias.upper()}.") == [canonical]


def test_repeated_overlapping_aliases_preserve_order() -> None:
    assert extract_skills("React.js Postgre SQL SQL JS " * 1800) == [
        "React", "PostgreSQL", "SQL", "JavaScript",
    ]


@pytest.mark.parametrize("word", ["éPython", "Pythoné", "Python_tools", "my_SQL"])
def test_skills_are_not_extracted_from_longer_words(word: str) -> None:
    assert extract_skills(word) == []
