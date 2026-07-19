"""Health report per docs/09 (GET /platform/health) and docs/05 (backup age surfacing).

Checks report honestly: anything not yet built reports "not_configured", never "ok".
"""

import shutil
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from serviceflow import __version__
from serviceflow.config import get_settings

router = APIRouter()

CheckState = Literal["ok", "warn", "fail", "not_configured"]

MIN_FREE_DISK_GB = 5


class HealthReport(BaseModel):
    status: Literal["ok", "degraded", "fail"]
    version: str
    checks: dict[str, CheckState]


def _check_database(database_url: str | None) -> CheckState:
    if database_url is None:
        return "not_configured"
    try:
        import sqlalchemy

        engine = sqlalchemy.create_engine(database_url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        return "ok"
    except Exception:
        return "fail"


def _check_disk() -> CheckState:
    usage = shutil.disk_usage(".")
    free_gb = usage.free / 1024**3
    return "ok" if free_gb >= MIN_FREE_DISK_GB else "warn"


@router.get("/health")
def health() -> HealthReport:
    settings = get_settings()
    checks: dict[str, CheckState] = {
        "database": _check_database(settings.database_url),
        "disk": _check_disk(),
        # Built in later stages (13_IMPLEMENTATION_PLAN): report honestly until then.
        "backup": "not_configured",
        "license": "not_configured",
        "jobs": "not_configured",
    }
    if "fail" in checks.values():
        status: Literal["ok", "degraded", "fail"] = "fail"
    elif "warn" in checks.values():
        status = "degraded"
    else:
        status = "ok"
    return HealthReport(status=status, version=__version__, checks=checks)
