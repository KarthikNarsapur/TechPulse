"""Environment-driven settings for TechPulse.

No credentials are shipped in source control. In AWS, prefer Lambda execution
roles and Secrets Manager for external integration secrets.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TechPulse"
    environment: str = "local"
    aws_region: str = "us-east-1"
    updates_table: str = "techpulse-updates"
    sources_table: str = "techpulse-sources"
    update_index_name: str = "technology-published-index"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="TECHPULSE_",
        env_file=".env",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
