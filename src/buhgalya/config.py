from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import AnyHttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DOCKER_SECRETS_DIR = "/run/secrets"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        secrets_dir=DOCKER_SECRETS_DIR if Path(DOCKER_SECRETS_DIR).is_dir() else None,
    )

    database_url: str = "postgresql+asyncpg://buhgalya:buhgalya@localhost:5432/buhgalya"
    bot_token: SecretStr | None = None
    api_base_url: AnyHttpUrl = "http://127.0.0.1:8000"
    default_workspace_id: UUID | None = None
    log_level: str = "INFO"

    @field_validator("default_workspace_id", mode="before")
    @classmethod
    def empty_workspace_id_is_none(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
