from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SERVICEFLOW_", env_file=".env", extra="ignore")

    debug: bool = False
    log_level: str = "INFO"
    # Comma-separated allowed CORS origins (e.g. the deployed frontend's exact
    # origin — no path, no trailing slash). Empty by default: local dev talks
    # to the backend through Vite's own proxy (same-origin from the browser's
    # perspective), so no CORS headers are needed there at all — see
    # serviceflow/main.py's create_app(), which only adds CORSMiddleware when
    # this is non-empty. A plain comma-separated string rather than a JSON
    # list keeps the Render dashboard value trivial to type (no escaping).
    cors_allow_origins: str = ""
    # Dev: docker-compose.dev.yml Postgres. Staging/prod: managed instance (ADR-017).
    database_url: str | None = None
    data_dir: Path = Path("data")
    # Local filesystem adapter (dev/local-edition); S3-compatible in Etap 3 (ADR-007).
    attachments_max_bytes: int = 10 * 1024 * 1024
    attachments_max_per_order: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
