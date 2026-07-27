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
    """Migrate as admin, then hand the app a NON-superuser role.

    RLS is bypassed by superusers, so the app must never connect as one — this is
    a deployment requirement (ADR-016/017), and the tests enforce it by mirroring it.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url

    assert TEST_DB_URL is not None
    os.environ["SERVICEFLOW_DATABASE_URL"] = TEST_DB_URL
    command.upgrade(Config("alembic.ini"), "head")

    admin = create_engine(TEST_DB_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(
            "DO $$ BEGIN IF NOT EXISTS "
            "(SELECT FROM pg_roles WHERE rolname = 'sf_app') THEN "
            "CREATE ROLE sf_app LOGIN PASSWORD 'sf-app-pw'; END IF; END $$"
        ))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO sf_app"))
        conn.execute(text(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sf_app"
        ))
        conn.execute(text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sf_app"
        ))
    admin.dispose()

    app_url = (
        make_url(TEST_DB_URL)
        .set(username="sf_app", password="sf-app-pw")
        .render_as_string(hide_password=False)
    )
    os.environ["SERVICEFLOW_DATABASE_URL"] = app_url
    return app_url


@pytest.fixture
def client(migrated_db: str, tmp_path) -> Iterator[TestClient]:  # noqa: ANN001
    from business_os.shared_kernel.db import get_engine
    from business_os.shared_kernel.storage import get_local_storage
    from serviceflow.config import get_settings
    from serviceflow.main import create_app

    os.environ["SERVICEFLOW_DATABASE_URL"] = migrated_db
    os.environ["SERVICEFLOW_DEBUG"] = "true"  # non-Secure cookies for TestClient
    os.environ["SERVICEFLOW_DATA_DIR"] = str(tmp_path)  # isolate uploaded files/test
    get_settings.cache_clear()
    get_local_storage.cache_clear()

    with TestClient(create_app()) as c:
        yield c

    # Clean slate between tests. TRUNCATE needs the table owner → admin URL,
    # and RLS-covered tables need the sledgehammer regardless.
    assert TEST_DB_URL is not None
    engine = get_engine(TEST_DB_URL)
    with engine.begin() as conn:
        # asset_types / order_statuses are migration seed data — never truncated.
        conn.execute(text(
            "TRUNCATE contact_records, attachments, tasks, timeline_events, "
            "accessory_items, labor_lines, part_lines, diagnoses, service_orders, "
            "document_sequences, asset_identifiers, assets, customers, audit_log, "
            "platform_audit_log, platform_admin_sessions, platform_admins, "
            "sessions, users, companies RESTART IDENTITY CASCADE"
        ))
    get_settings.cache_clear()
    get_local_storage.cache_clear()
