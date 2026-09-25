"""Migration #21 regression test (Wave 2 Issue 5: "testing" removed as an
active order status, folded into "repair").

Same technique as test_migration_0018/0020: migrate to the revision
immediately before 0021, seed pre-migration state by hand (a real
`service_orders` row with `status_code = 'testing'`, plus a historical
timeline event referencing "testing", the way a real pre-existing
deployment's data looks), continue to head, and verify the result against a
throwaway database — not model metadata alone.
"""

import os
import uuid
from collections.abc import Iterator

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
def pre_0021_db() -> Iterator[str]:
    """A throwaway database migrated only to revision 0020 — real
    pre-migration schema, "testing" still a valid order_statuses row."""
    base_url = os.environ["SERVICEFLOW_TEST_DATABASE_URL"]
    db_name = f"migration_0021_regression_{uuid.uuid4().hex[:12]}"
    admin_url = make_url(base_url).set(database="postgres")

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()

    test_url = make_url(base_url).set(database=db_name).render_as_string(hide_password=False)
    saved_env = os.environ.get("SERVICEFLOW_DATABASE_URL")
    os.environ["SERVICEFLOW_DATABASE_URL"] = test_url
    command.upgrade(Config("alembic.ini"), "0020")

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


def _seed_pre_migration_order(url: str, status_code: str) -> tuple[uuid.UUID, uuid.UUID]:
    """A company, user, asset type, customer, asset, one service order in
    `status_code`, and a historical timeline event recording an earlier
    transition *into* "testing" — the way a real pre-0021 deployment's data
    looks. Returns (order_id, timeline_event_id)."""
    engine = create_engine(url)
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    asset_type_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    order_id = uuid.uuid4()
    event_id = uuid.uuid4()

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO companies (id, name) VALUES (:id, 'Сервиз Преди Миграция')"
        ), {"id": company_id})
        conn.execute(text(
            "INSERT INTO users (id, company_id, name, email, password_hash, is_owner) "
            "VALUES (:id, :company_id, 'Собственик', 'owner@pre21.bg', 'x', true)"
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
            "complaint, status_code, created_by) VALUES "
            "(:id, :company_id, '2026-00001', :customer_id, :asset_id, "
            "'Не се включва', :status_code, :user_id)"
        ), {
            "id": order_id, "company_id": company_id, "customer_id": customer_id,
            "asset_id": asset_id, "user_id": user_id, "status_code": status_code,
        })
        conn.execute(text(
            "INSERT INTO timeline_events (id, company_id, order_id, event_type, "
            "actor_user_id, data) VALUES "
            "(:id, :company_id, :order_id, 'status_changed', :user_id, "
            "CAST(:data AS jsonb))"
        ), {
            "id": event_id, "company_id": company_id, "order_id": order_id,
            "user_id": user_id, "data": '{"from": "repair", "to": "testing"}',
        })

    engine.dispose()
    return order_id, event_id


def test_upgrade_through_0021_reassigns_testing_orders_to_repair(pre_0021_db: str) -> None:
    order_id, _event_id = _seed_pre_migration_order(pre_0021_db, "testing")

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0021_db)
    with engine.connect() as conn:
        status = conn.execute(
            text("SELECT status_code FROM service_orders WHERE id = :id"), {"id": order_id},
        ).scalar_one()
    engine.dispose()
    assert status == "repair"


def test_upgrade_through_0021_drops_the_testing_order_status_row(pre_0021_db: str) -> None:
    _seed_pre_migration_order(pre_0021_db, "received")

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0021_db)
    with engine.connect() as conn:
        remaining = conn.execute(
            text("SELECT code FROM order_statuses ORDER BY code"),
        ).scalars().all()
    engine.dispose()
    assert "testing" not in remaining
    assert set(remaining) == {
        "received", "diagnostics", "waiting_customer", "waiting_parts", "repair",
        "ready", "completed", "declined", "unrepairable", "cancelled",
    }


def test_upgrade_through_0021_leaves_orders_in_other_statuses_untouched(pre_0021_db: str) -> None:
    order_id, _ = _seed_pre_migration_order(pre_0021_db, "repair")

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0021_db)
    with engine.connect() as conn:
        status = conn.execute(
            text("SELECT status_code FROM service_orders WHERE id = :id"), {"id": order_id},
        ).scalar_one()
    engine.dispose()
    assert status == "repair"


def test_upgrade_through_0021_preserves_historical_timeline_event_data(pre_0021_db: str) -> None:
    """BR-5: append-only history is never rewritten. A timeline event that
    recorded a real, historical "-> testing" transition keeps saying so —
    the migration changes only the order's *current* status_code, never
    past event data."""
    _order_id, event_id = _seed_pre_migration_order(pre_0021_db, "testing")

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0021_db)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT event_type, data FROM timeline_events WHERE id = :id"),
            {"id": event_id},
        ).one()
    engine.dispose()
    assert row.event_type == "status_changed"
    assert row.data == {"from": "repair", "to": "testing"}
