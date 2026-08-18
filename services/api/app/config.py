"""Runtime configuration. Values come from the environment / .env (never committed)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "scoutglobe-api"
    app_version: str = "0.1.0"

    # Port 5435 keeps the docker Postgres out of the way of a locally installed one.
    database_url: str = "postgresql+psycopg://scoutglobe:scoutglobe@localhost:5435/scoutglobe"

    # Comma-separated list of allowed browser origins.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
