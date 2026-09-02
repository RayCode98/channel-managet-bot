from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    platform_admin_ids: frozenset[int] = Field(default_factory=frozenset)
    default_timezone: str = "America/Mexico_City"
    max_channels_per_workspace: int = 30
    worker_poll_seconds: float = 2.0

    @field_validator("platform_admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value):
        if value in (None, ""):
            return frozenset()
        if isinstance(value, int):
            return frozenset({value})
        if isinstance(value, str):
            return frozenset(int(item.strip()) for item in value.split(",") if item.strip())
        return frozenset(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
