from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "IoT Security Demo"
    environment: str = Field(default="local", description="Runtime environment name.")
    database_url: str = Field(
        default="sqlite:///./data/iot_demo.db",
        description="SQLAlchemy database URI.",
    )
    jwt_secret_key: str = Field(
        default="super-hiper-secret-token",
        description="Signing key for user access tokens.",
    )
    jwt_refresh_secret_key: str = Field(
        default="refresh-super-hiper-secret-token",
        description="Signing key for user refresh tokens.",
    )
    jwt_device_secret_key: str = Field(
        default="device-secret",
        description="Signing key for device access tokens.",
    )
    jwt_algorithm: str = "HS256"
    access_token_exp_minutes: int = 15
    refresh_token_exp_minutes: int = 60 * 24 * 7
    device_token_exp_minutes: int = 5
    data_payload_limit_bytes: int = 2048
    min_seconds_between_readings: float = 1.0
    max_readings_page_size: int = 100
    default_rate_limit_seconds: float = 1.0
    log_retention_days: int = 30
    telemetry_simulation_enabled: bool = Field(
        default=True,
        description="Toggle background telemetry generator.",
    )
    api_cors_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins for the API.",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def database_path(self) -> Path | None:
        """Return filesystem path for SQLite database if applicable."""
        if self.database_url.startswith("sqlite:///"):
            raw_path = self.database_url.replace("sqlite:///", "", 1)
            return Path(raw_path).resolve()
        if self.database_url.startswith("sqlite://"):
            raw_path = self.database_url.replace("sqlite://", "", 1)
            return Path(raw_path).resolve()
        return None


@lru_cache
def get_settings() -> Settings:
    """Return Settings singleton."""
    return Settings()
