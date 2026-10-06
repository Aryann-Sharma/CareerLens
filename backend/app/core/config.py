from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

DEVELOPMENT_AUTH_SECRET = "development-only-secret-change-before-production"


class Settings(BaseSettings):
    app_name: str = "CareerLens"
    app_version: str = "0.1.0"
    environment: Literal["development", "testing", "production"] = "development"
    database_url: str = "sqlite:///./careerlens.db"
    auth_secret_key: str = Field(
        default=DEVELOPMENT_AUTH_SECRET,
        min_length=32,
    )
    auth_token_expire_minutes: int = Field(default=60, ge=5, le=10_080)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value: object) -> object:
        return value.strip().casefold() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment.casefold() != "production":
            return self

        if self.auth_secret_key == DEVELOPMENT_AUTH_SECRET:
            raise ValueError("AUTH_SECRET_KEY must be set in production")

        try:
            driver = make_url(self.database_url).drivername
        except ArgumentError as error:
            raise ValueError("DATABASE_URL must be a valid database URL") from error
        if driver != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use postgresql+psycopg:// in production")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
