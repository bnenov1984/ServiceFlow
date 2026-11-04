"""Migration #22 regression test (Wave 2 Issue 33: part_lines.state
simplified to ordered/installed).

Same technique as test_migration_0018/0020/0021: migrate to the revision
immediately before 0022, seed pre-migration state by hand (part_lines rows
in every one of the old 5-state model's values, the way a real pre-existing
company's data looks), continue to head, and verify the backfill mapping —
not model metadata alone.
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
def pre_0022_db() -> Iterator[str]:
    """A throwaway database migrated only to revision 0021 — real
    pre-migration schema, the original 5-state `ck_part_lines_state` CHECK
    constraint still in place."""
    base_url = os.environ["SERVICEFLOW_TEST_DATABASE_URL"]
    db_name = f"migration_0022_regression_{uuid.uuid4().hex[:12]}"
    admin_url = make_url(base_url).set(database="postgres")

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()

    test_url = make_url(base_url).set(database=db_name).render_as_string(hide_password=False)
    saved_env = os.environ.get("SERVICEFLOW_DATABASE_URL")
    os.environ["SERVICEFLOW_DATABASE_URL"] = test_url
    command.upgrade(Config("alembic.ini"), "0021")

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


def _seed_pre_migration_order_with_parts(url: str) -> dict[str, uuid.UUID]:
    """One order, five part lines — one per legacy state — plus a historical
    timeline event referencing "received" (must survive untouched). Returns
    {old_state: part_line_id}."""
    engine = create_engine(url)
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    asset_type_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    order_id = uuid.uuid4()
    event_id = uuid.uuid4()
    line_ids = {state: uuid.uuid4() for state in
                ("needed", "ordered", "received", "installed", "removed")}

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO companies (id, name) VALUES (:id, 'Сервиз Преди Миграция')"
        ), {"id": company_id})
        conn.execute(text(
            "INSERT INTO users (id, company_id, name, email, password_hash, is_owner) "
            "VALUES (:id, :company_id, 'Собственик', 'owner@pre22.bg', 'x', true)"
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
            "'Не се включва', 'repair', :user_id)"
        ), {
            "id": order_id, "company_id": company_id, "customer_id": customer_id,
            "asset_id": asset_id, "user_id": user_id,
        })
        for state, line_id in line_ids.items():
            conn.execute(text(
                "INSERT INTO part_lines (id, company_id, order_id, name, state) "
                "VALUES (:id, :company_id, :order_id, :name, :state)"
            ), {
                "id": line_id, "company_id": company_id, "order_id": order_id,
                "name": f"Част ({state})", "state": state,
            })
        conn.execute(text(
            "INSERT INTO timeline_events (id, company_id, order_id, event_type, "
            "actor_user_id, data) VALUES "
            "(:id, :company_id, :order_id, 'part_received', :user_id, "
            "CAST(:data AS jsonb))"
        ), {
            "id": event_id, "company_id": company_id, "order_id": order_id,
            "user_id": user_id, "data": '{"name": "Част", "from": "ordered", "to": "received"}',
        })

    engine.dispose()
    return line_ids


def _states_by_id(url: str, line_ids: dict[str, uuid.UUID]) -> dict[str, str]:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, state FROM part_lines WHERE id = ANY(:ids)"
        ), {"ids": list(line_ids.values())}).all()
    engine.dispose()
    by_id = {row.id: row.state for row in rows}
    return {old_state: by_id[line_id] for old_state, line_id in line_ids.items()}


def test_upgrade_through_0022_applies_the_legacy_mapping(pre_0022_db: str) -> None:
    line_ids = _seed_pre_migration_order_with_parts(pre_0022_db)

    command.upgrade(Config("alembic.ini"), "head")

    new_states = _states_by_id(pre_0022_db, line_ids)
    assert new_states == {
        "needed": "ordered",
        "ordered": "ordered",
        "received": "ordered",
        "installed": "installed",
        "removed": "ordered",
    }


def test_upgrade_through_0022_new_check_constraint_rejects_old_states(pre_0022_db: str) -> None:
    line_ids = _seed_pre_migration_order_with_parts(pre_0022_db)
    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0022_db)
    any_line_id = next(iter(line_ids.values()))
    with pytest.raises(Exception, match="ck_part_lines_state"), engine.begin() as conn:
        conn.execute(text(
            "UPDATE part_lines SET state = 'needed' WHERE id = :id"
        ), {"id": any_line_id})
    engine.dispose()


def test_upgrade_through_0022_new_rows_default_to_ordered(pre_0022_db: str) -> None:
    """The column-level DEFAULT itself (not just the model's Python-side
    default) must reflect the new state — a raw INSERT that omits `state`
    entirely, exactly like ORM-level `PartLine(...)` does, must land on
    "ordered". Pinned to "0022" itself, not "head" — order-workflow-revamp
    WP-J's migration 0038 changes this same column's server_default again
    (to "issued"), which is a separate, later fact this test must not
    accidentally re-assert; see test_migration_0038_part_line_state_and_
    warranty.py's own equivalent test for that one."""
    _seed_pre_migration_order_with_parts(pre_0022_db)
    command.upgrade(Config("alembic.ini"), "0022")

    engine = create_engine(pre_0022_db)
    with engine.begin() as conn:
        existing_order = conn.execute(
            text("SELECT id, company_id FROM service_orders LIMIT 1")
        ).one()
        new_line_id = uuid.uuid4()
        conn.execute(text(
            "INSERT INTO part_lines (id, company_id, order_id, name) "
            "VALUES (:id, :company_id, :order_id, 'Нова част')"
        ), {
            "id": new_line_id, "company_id": existing_order.company_id,
            "order_id": existing_order.id,
        })
        state = conn.execute(
            text("SELECT state FROM part_lines WHERE id = :id"), {"id": new_line_id},
        ).scalar_one()
    engine.dispose()
    assert state == "ordered"


def test_upgrade_through_0022_preserves_historical_timeline_event_data(pre_0022_db: str) -> None:
    """BR-5: append-only history is never rewritten. A `part_received` event
    from before the simplification keeps saying "received" — the migration
    changes only part_lines' *current* state column, never past event data."""
    _seed_pre_migration_order_with_parts(pre_0022_db)

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0022_db)
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT event_type, data FROM timeline_events WHERE event_type = 'part_received'"
        )).one()
    engine.dispose()
    assert row.event_type == "part_received"
    assert row.data == {"name": "Част", "from": "ordered", "to": "received"}
