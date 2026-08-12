from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment configuration shared by the Python services."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "reminder-service"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://reminder:reminder@localhost:5432/reminder_app"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    jwt_secret: str = "development-only-change-this-secret"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = Field(default=15, gt=0)
    refresh_token_ttl_days: int = Field(default=30, gt=0)
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    auth_service_url: str = "http://auth-service:8000"
    user_service_url: str = "http://user-service:8000"
    reminder_service_url: str = "http://reminder-service:8000"
    initial_admin_email: str | None = None
    initial_admin_password: str | None = None
    initial_admin_name: str = "System Administrator"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
