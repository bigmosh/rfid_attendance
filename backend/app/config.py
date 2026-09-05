"""Environment-based backend configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings supplied by the shell, Docker, or Coolify environment."""

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str
    app_timezone: str = "Europe/Helsinki"
    cors_origins: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self):
        """Return the configured comma-separated origin allowlist."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings():
    """Return the process-wide settings instance."""
    return Settings()
