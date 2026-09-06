from functools import lru_cache
from uuid import UUID

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://buhgalya:buhgalya@localhost:5432/buhgalya"
    bot_token: SecretStr | None = None
    api_base_url: AnyHttpUrl = "http://localhost:8000"
    default_workspace_id: UUID | None = None
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
