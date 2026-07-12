"""Integration tests run against a real PostgreSQL (docs/12: no mocked databases).

Set SERVICEFLOW_TEST_DATABASE_URL to enable them; without it, DB-marked tests skip
(unit tests always run). CI provides a postgres service; locally use
docker-compose.dev.yml or the parked spike instance.
"""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

TEST_DB_URL = os.environ.get("SERVICEFLOW_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def migrated_db() -> str:
    assert TEST_DB_URL is not None
    os.environ["SERVICEFLOW_DATABASE_URL"] = TEST_DB_URL
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    return TEST_DB_URL


@pytest.fixture
def client(migrated_db: str) -> Iterator[TestClient]:
    from serviceflow.config import get_settings
    from serviceflow.main import create_app
    from serviceflow.shared_kernel.db import get_engine

    os.environ["SERVICEFLOW_DATABASE_URL"] = migrated_db
    os.environ["SERVICEFLOW_DEBUG"] = "true"  # non-Secure cookies for TestClient
    get_settings.cache_clear()

    with TestClient(create_app()) as c:
        yield c

    # Clean slate between tests: truncate everything except alembic_version.
    engine = get_engine(migrated_db)
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE audit_log, sessions, users, companies RESTART IDENTITY CASCADE"
        ))
    get_settings.cache_clear()
