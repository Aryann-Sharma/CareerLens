from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, inspect, text

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
        command.upgrade(config, "0002")
        engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        metadata = MetaData()
        analyses = Table("analyses", metadata, autoload_with=engine)
        with engine.begin() as connection:
            result = connection.execute(
                analyses.insert().values(
                    job_description="Legacy analysis",
                    user_skills=["Python"],
                    extracted_skills=["Python"],
                    matched_skills=["Python"],
                    missing_skills=[],
                    match_score=100,
                )
            )
            legacy_analysis_id = result.inserted_primary_key[0]

        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert "analyses" in inspector.get_table_names()
        assert "users" in inspector.get_table_names()
        assert {column["name"] for column in inspector.get_columns("analyses")} == {
            "id",
            "user_id",
            "job_description",
            "user_skills",
            "extracted_skills",
            "matched_skills",
            "missing_skills",
            "match_score",
            "created_at",
        }
        assert {index["name"] for index in inspector.get_indexes("analyses")} == {
            "ix_analyses_created_at",
            "ix_analyses_user_id_created_at",
        }
        foreign_keys = inspector.get_foreign_keys("analyses")
        assert foreign_keys[0]["name"] == "fk_analyses_user_id_users"
        assert foreign_keys[0]["referred_table"] == "users"
        with engine.connect() as connection:
            legacy_row = connection.execute(
                text(
                    "SELECT job_description, user_id FROM analyses "
                    "WHERE id = :analysis_id"
                ),
                {"analysis_id": legacy_analysis_id},
            ).one()
        assert legacy_row.job_description == "Legacy analysis"
        assert legacy_row.user_id is None
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
