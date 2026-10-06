from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_AUTH_SECRET = "development-only-secret-change-before-production"


class Settings(BaseSettings):
    app_name: str = "CareerLens"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = "sqlite:///./careerlens.db"
    auth_secret_key: str = Field(
        default=DEVELOPMENT_AUTH_SECRET,
        min_length=32,
    )
    auth_token_expire_minutes: int = Field(default=60, ge=5, le=10_080)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment.casefold() != "production":
            return self

        if self.auth_secret_key == DEVELOPMENT_AUTH_SECRET:
            raise ValueError("AUTH_SECRET_KEY must be set in production")

        if not self.database_url.startswith("postgresql"):
            raise ValueError("DATABASE_URL must use PostgreSQL in production")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
