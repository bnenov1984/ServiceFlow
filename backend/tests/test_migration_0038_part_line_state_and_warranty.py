"""Migration #38 regression test (order-workflow-revamp WP-J: part_lines
gains a third state and swaps `warranty_days` for a boolean `has_warranty`).

Same technique as test_migration_0022_simplify_part_states.py: migrate to
the revision immediately before 0038, seed pre-migration state by hand (a
real pre-existing company's `warranty_days` values: NULL, explicit 0, and
positive), continue to head, and verify the backfill — not model metadata
alone.
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
def pre_0038_db() -> Iterator[str]:
    """A throwaway database migrated only to revision 0037 — real
    pre-migration schema: `part_lines.state` still CHECK-constrained to
    ('ordered', 'installed') and `warranty_days` still present."""
    base_url = os.environ["SERVICEFLOW_TEST_DATABASE_URL"]
    db_name = f"migration_0038_regression_{uuid.uuid4().hex[:12]}"
    admin_url = make_url(base_url).set(database="postgres")

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()

    test_url = make_url(base_url).set(database=db_name).render_as_string(hide_password=False)
    saved_env = os.environ.get("SERVICEFLOW_DATABASE_URL")
    os.environ["SERVICEFLOW_DATABASE_URL"] = test_url
    command.upgrade(Config("alembic.ini"), "0037")

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
    """One order, three part lines — one per `warranty_days` shape (NULL,
    explicit 0, positive) — all in the pre-WP-J `state="ordered"`. Returns
    {label: part_line_id}."""
    engine = create_engine(url)
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    asset_type_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    order_id = uuid.uuid4()
    line_ids = {"null": uuid.uuid4(), "zero": uuid.uuid4(), "positive": uuid.uuid4()}
    warranty_by_label: dict[str, int | None] = {"null": None, "zero": 0, "positive": 90}

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO companies (id, name) VALUES (:id, 'Сервиз Преди Миграция')"
        ), {"id": company_id})
        conn.execute(text(
            "INSERT INTO users (id, company_id, name, email, password_hash, is_owner) "
            "VALUES (:id, :company_id, 'Собственик', 'owner@pre38.bg', 'x', true)"
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
        for label, line_id in line_ids.items():
            conn.execute(text(
                "INSERT INTO part_lines (id, company_id, order_id, name, state, "
                "warranty_days) VALUES "
                "(:id, :company_id, :order_id, :name, 'ordered', :warranty_days)"
            ), {
                "id": line_id, "company_id": company_id, "order_id": order_id,
                "name": f"Част ({label})", "warranty_days": warranty_by_label[label],
            })

    engine.dispose()
    return line_ids


def _has_warranty_by_id(url: str, line_ids: dict[str, uuid.UUID]) -> dict[str, bool]:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, has_warranty FROM part_lines WHERE id = ANY(:ids)"
        ), {"ids": list(line_ids.values())}).all()
    engine.dispose()
    by_id = {row.id: row.has_warranty for row in rows}
    return {label: by_id[line_id] for label, line_id in line_ids.items()}


def test_upgrade_through_0038_backfills_has_warranty_from_warranty_days(
    pre_0038_db: str,
) -> None:
    line_ids = _seed_pre_migration_order_with_parts(pre_0038_db)

    command.upgrade(Config("alembic.ini"), "head")

    assert _has_warranty_by_id(pre_0038_db, line_ids) == {
        "null": True, "zero": False, "positive": True,
    }


def test_upgrade_through_0038_drops_warranty_days_column(pre_0038_db: str) -> None:
    _seed_pre_migration_order_with_parts(pre_0038_db)
    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0038_db)
    with pytest.raises(Exception, match="warranty_days"), engine.begin() as conn:
        conn.execute(text("SELECT warranty_days FROM part_lines LIMIT 1"))
    engine.dispose()


def test_upgrade_through_0038_preserves_existing_state_values(pre_0038_db: str) -> None:
    """No backfill needed for `state` (unlike 0022): "ordered" is still a
    valid, unchanged value under the widened constraint."""
    line_ids = _seed_pre_migration_order_with_parts(pre_0038_db)
    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0038_db)
    with engine.connect() as conn:
        states = conn.execute(text(
            "SELECT DISTINCT state FROM part_lines WHERE id = ANY(:ids)"
        ), {"ids": list(line_ids.values())}).scalars().all()
    engine.dispose()
    assert set(states) == {"ordered"}


def test_upgrade_through_0038_new_check_constraint_accepts_issued(pre_0038_db: str) -> None:
    line_ids = _seed_pre_migration_order_with_parts(pre_0038_db)
    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0038_db)
    any_line_id = next(iter(line_ids.values()))
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE part_lines SET state = 'issued' WHERE id = :id"
        ), {"id": any_line_id})
        state = conn.execute(
            text("SELECT state FROM part_lines WHERE id = :id"), {"id": any_line_id},
        ).scalar_one()
    engine.dispose()
    assert state == "issued"


def test_upgrade_through_0038_new_rows_default_to_issued_and_has_warranty_true(
    pre_0038_db: str,
) -> None:
    """Column-level DEFAULTs (not just the model's Python-side defaults) —
    a raw INSERT that omits both columns, exactly like ORM-level
    `PartLine(...)` does, must land on "issued"/true."""
    _seed_pre_migration_order_with_parts(pre_0038_db)
    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0038_db)
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
        row = conn.execute(
            text("SELECT state, has_warranty FROM part_lines WHERE id = :id"),
            {"id": new_line_id},
        ).one()
    engine.dispose()
    assert row.state == "issued"
    assert row.has_warranty is True
