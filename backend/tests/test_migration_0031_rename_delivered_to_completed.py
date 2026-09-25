"""Migration #31 regression test (Wave 4 audit correction: "delivered"/
"Предадена" renamed to "completed"/"Приключена").

Same technique as test_migration_0018/0020/0021/0022: migrate to the
revision immediately before 0031, seed pre-migration state by hand (a real
`service_orders` row with `status_code = 'delivered'` and `delivered_at`
set, plus a historical timeline event recording an "order_delivered", the
way a real pre-existing deployment's data looks), continue to head, and
verify the result against a throwaway database — not model metadata alone.
"""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


@pytest.fixture
def pre_0031_db() -> Iterator[str]:
    """A throwaway database migrated only to revision 0030 — real
    pre-migration schema, "delivered" still the terminal-success status and
    `delivered_at` still the column name."""
    base_url = os.environ["SERVICEFLOW_TEST_DATABASE_URL"]
    db_name = f"migration_0031_regression_{uuid.uuid4().hex[:12]}"
    admin_url = make_url(base_url).set(database="postgres")

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()

    test_url = make_url(base_url).set(database=db_name).render_as_string(hide_password=False)
    saved_env = os.environ.get("SERVICEFLOW_DATABASE_URL")
    os.environ["SERVICEFLOW_DATABASE_URL"] = test_url
    command.upgrade(Config("alembic.ini"), "0030")

    try:
        yield test_url
    finally:
        if saved_env is not None:
            os.environ["SERVICEFLOW_DATABASE_URL"] = saved_env
        else:
            os.environ.pop("SERVICEFLOW_DATABASE_URL", None)

        admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"
            ))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        admin.dispose()


def _seed_pre_migration_delivered_order(url: str) -> tuple[uuid.UUID, uuid.UUID, datetime]:
    """A company, user, asset type, customer, asset, one service order
    already `status_code = 'delivered'` with `delivered_at` set, and a
    historical timeline event recording the earlier "order_delivered" —
    the way a real pre-0031 deployment's data looks. Returns
    (order_id, timeline_event_id, delivered_at)."""
    engine = create_engine(url)
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    asset_type_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    order_id = uuid.uuid4()
    event_id = uuid.uuid4()
    delivered_at = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO companies (id, name) VALUES (:id, 'Сервиз Преди Миграция')"
        ), {"id": company_id})
        conn.execute(text(
            "INSERT INTO users (id, company_id, name, email, password_hash, is_owner) "
            "VALUES (:id, :company_id, 'Собственик', 'owner@pre31.bg', 'x', true)"
        ), {"id": user_id, "company_id": company_id})
        conn.execute(text(
            "INSERT INTO asset_types (id, company_id, code, name_bg, business_profile) "
            "VALUES (:id, :company_id, 'phone', 'Телефон', 'generic_repair')"
        ), {"id": asset_type_id, "company_id": company_id})
        conn.execute(text(
            "INSERT INTO customers (id, company_id, name, phone, phone_normalized, "
            "name_translit) VALUES "
            "(:id, :company_id, 'Клиент', '0888000111', '0888000111', 'Klient')"
        ), {"id": customer_id, "company_id": company_id})
        conn.execute(text(
            "INSERT INTO assets (id, company_id, customer_id, asset_type_id, label) "
            "VALUES (:id, :company_id, :customer_id, :asset_type_id, 'iPhone')"
        ), {
            "id": asset_id, "company_id": company_id, "customer_id": customer_id,
            "asset_type_id": asset_type_id,
        })
        conn.execute(text(
            "INSERT INTO service_orders (id, company_id, number, customer_id, asset_id, "
            "complaint, status_code, delivered_at, created_by) VALUES "
            "(:id, :company_id, '2026-00001', :customer_id, :asset_id, "
            "'Не се включва', 'delivered', :delivered_at, :user_id)"
        ), {
            "id": order_id, "company_id": company_id, "customer_id": customer_id,
            "asset_id": asset_id, "user_id": user_id, "delivered_at": delivered_at,
        })
        conn.execute(text(
            "INSERT INTO timeline_events (id, company_id, order_id, event_type, "
            "actor_user_id, data) VALUES "
            "(:id, :company_id, :order_id, 'order_delivered', :user_id, "
            "CAST(:data AS jsonb))"
        ), {
            "id": event_id, "company_id": company_id, "order_id": order_id,
            "user_id": user_id, "data": '{"warranty_days": 90}',
        })

    engine.dispose()
    return order_id, event_id, delivered_at


def test_upgrade_through_0031_reassigns_delivered_orders_to_completed(pre_0031_db: str) -> None:
    order_id, _event_id, _delivered_at = _seed_pre_migration_delivered_order(pre_0031_db)

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0031_db)
    with engine.connect() as conn:
        status = conn.execute(
            text("SELECT status_code FROM service_orders WHERE id = :id"), {"id": order_id},
        ).scalar_one()
    engine.dispose()
    assert status == "completed"


def test_upgrade_through_0031_drops_the_delivered_order_status_row(pre_0031_db: str) -> None:
    _seed_pre_migration_delivered_order(pre_0031_db)

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0031_db)
    with engine.connect() as conn:
        remaining = conn.execute(
            text("SELECT code, name_bg FROM order_statuses ORDER BY code"),
        ).all()
    engine.dispose()
    by_code = {row.code: row.name_bg for row in remaining}
    assert "delivered" not in by_code
    assert by_code["completed"] == "Приключена"
    assert set(by_code) == {
        "received", "diagnostics", "waiting_customer", "waiting_parts", "repair",
        "ready", "completed", "declined", "unrepairable", "cancelled",
    }


def test_upgrade_through_0031_renames_delivered_at_column_preserving_data(
    pre_0031_db: str,
) -> None:
    order_id, _event_id, delivered_at = _seed_pre_migration_delivered_order(pre_0031_db)

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0031_db)
    with engine.connect() as conn:
        completed_at = conn.execute(
            text("SELECT completed_at FROM service_orders WHERE id = :id"), {"id": order_id},
        ).scalar_one()
    engine.dispose()
    # `service_orders.delivered_at`/`completed_at` is `timestamp without time
    # zone` — Postgres hands back a naive datetime regardless of what tzinfo
    # the insert carried, so compare against the naive equivalent.
    assert completed_at == delivered_at.replace(tzinfo=None)


def test_upgrade_through_0031_preserves_historical_timeline_event_data(pre_0031_db: str) -> None:
    """BR-5: append-only history is never rewritten. A timeline event that
    recorded a real, historical "order_delivered" transition keeps saying
    so — the migration changes only the order's *current* status_code and
    the *column name* it's stored under, never past event data."""
    _order_id, event_id, _delivered_at = _seed_pre_migration_delivered_order(pre_0031_db)

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0031_db)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT event_type, data FROM timeline_events WHERE id = :id"),
            {"id": event_id},
        ).one()
    engine.dispose()
    assert row.event_type == "order_delivered"
    assert row.data == {"warranty_days": 90}
