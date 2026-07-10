from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SERVICEFLOW_", env_file=".env", extra="ignore")

    debug: bool = False
    log_level: str = "INFO"
    # Unset until the ADR-002 Stage-0 gate passes; health reports it honestly.
    database_url: str | None = None
    data_dir: Path = Path("data")


@lru_cache
def get_settings() -> Settings:
    return Settings()
