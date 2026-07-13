from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SERVICEFLOW_", env_file=".env", extra="ignore")

    debug: bool = False
    log_level: str = "INFO"
    # Dev: docker-compose.dev.yml Postgres. Staging/prod: managed instance (ADR-017).
    database_url: str | None = None
    data_dir: Path = Path("data")
    # Local filesystem adapter (dev/local-edition); S3-compatible in Etap 3 (ADR-007).
    attachments_max_bytes: int = 10 * 1024 * 1024
    attachments_max_per_order: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
