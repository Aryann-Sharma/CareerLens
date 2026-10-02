from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from backend.app.core.config import get_settings


def test_migrations_upgrade_and_downgrade(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "migration-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()

    project_root = Path(__file__).resolve().parents[2]
    config = Config(project_root / "alembic.ini")

    try:
        command.upgrade(config, "head")

        engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        inspector = inspect(engine)
        assert "analyses" in inspector.get_table_names()
        assert "users" in inspector.get_table_names()
        assert {column["name"] for column in inspector.get_columns("analyses")} == {
            "id",
            "job_description",
            "user_skills",
            "extracted_skills",
            "matched_skills",
            "missing_skills",
            "match_score",
            "created_at",
        }
        assert inspector.get_indexes("analyses")[0]["name"] == (
            "ix_analyses_created_at"
        )
        assert {column["name"] for column in inspector.get_columns("users")} == {
            "id",
            "email",
            "password_hash",
            "created_at",
        }
        assert inspector.get_unique_constraints("users")[0]["name"] == (
            "uq_users_email"
        )

        command.downgrade(config, "base")
        remaining_tables = inspect(engine).get_table_names()
        assert "analyses" not in remaining_tables
        assert "users" not in remaining_tables
        engine.dispose()
    finally:
        get_settings.cache_clear()
