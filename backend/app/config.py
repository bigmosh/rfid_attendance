"""Environment-based backend configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings supplied by the shell, Docker, or Coolify environment."""

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings():
    """Return the process-wide settings instance."""
    return Settings()
