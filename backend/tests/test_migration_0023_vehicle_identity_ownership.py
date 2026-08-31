"""Migration #23 regression test (Wave 3 Issue 20: vehicle identity +
ownership history). Same technique as test_migration_0020/0021/0022: migrate
to the revision immediately before 0023, seed pre-migration state by hand,
continue to head, and verify the actual backfill/constraint behavior."""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


@pytest.fixture
def pre_0023_db() -> Iterator[str]:
    """A throwaway database migrated only to revision 0022 — real
    pre-migration schema, no asset_ownership table and no VIN uniqueness
    index yet."""
    base_url = os.environ["SERVICEFLOW_TEST_DATABASE_URL"]
    db_name = f"migration_0023_regression_{uuid.uuid4().hex[:12]}"
    admin_url = make_url(base_url).set(database="postgres")

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()

    test_url = make_url(base_url).set(database=db_name).render_as_string(hide_password=False)
    saved_env = os.environ.get("SERVICEFLOW_DATABASE_URL")
    os.environ["SERVICEFLOW_DATABASE_URL"] = test_url
    command.upgrade(Config("alembic.ini"), "0022")

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


def _seed_company_and_customer(conn: Connection, company_name: str,
                               email: str) -> tuple[uuid.UUID, uuid.UUID]:
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    conn.execute(text(
        "INSERT INTO companies (id, name) VALUES (:id, :name)"
    ), {"id": company_id, "name": company_name})
    conn.execute(text(
        "INSERT INTO users (id, company_id, name, email, password_hash, is_owner) "
        "VALUES (:id, :company_id, 'Собственик', :email, 'x', true)"
    ), {"id": user_id, "company_id": company_id, "email": email})
    conn.execute(text(
        "INSERT INTO customers (id, company_id, name, phone, phone_normalized, name_translit) "
        "VALUES (:id, :company_id, 'Клиент', '0888000111', '0888000111', 'Klient')"
    ), {"id": customer_id, "company_id": company_id})
    return company_id, customer_id


def _seed_vehicle_asset(conn: Connection, company_id: uuid.UUID, customer_id: uuid.UUID,
                        vin_normalized: str, created_at: datetime) -> uuid.UUID:
    asset_type_id = conn.execute(text(
        "SELECT id FROM asset_types WHERE company_id = :company_id AND code = 'vehicle'"
    ), {"company_id": company_id}).scalar()
    if asset_type_id is None:
        asset_type_id = uuid.uuid4()
        conn.execute(text(
            "INSERT INTO asset_types (id, company_id, code, name_bg, business_profile) "
            "VALUES (:id, :company_id, 'vehicle', 'Автомобил', 'generic_repair')"
        ), {"id": asset_type_id, "company_id": company_id})
    asset_id = uuid.uuid4()
    conn.execute(text(
        "INSERT INTO assets (id, company_id, customer_id, asset_type_id, label, "
        "created_at, updated_at) VALUES "
        "(:id, :company_id, :customer_id, :asset_type_id, 'Volkswagen Golf', "
        ":created_at, :created_at)"
    ), {
        "id": asset_id, "company_id": company_id, "customer_id": customer_id,
        "asset_type_id": asset_type_id, "created_at": created_at,
    })
    conn.execute(text(
        "INSERT INTO asset_identifiers (id, company_id, asset_id, kind, value, "
        "value_normalized) VALUES (:id, :company_id, :asset_id, 'vin', :value, :normalized)"
    ), {
        "id": uuid.uuid4(), "company_id": company_id, "asset_id": asset_id,
        "value": vin_normalized, "normalized": vin_normalized,
    })
    return asset_id


def test_upgrade_through_0023_backfills_one_open_ownership_row_per_asset(
    pre_0023_db: str,
) -> None:
    engine = create_engine(pre_0023_db)
    created_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
    with engine.begin() as conn:
        company_id, customer_id = _seed_company_and_customer(
            conn, "Сервиз Преди 23", "pre23@x.bg",
        )
        asset_id = _seed_vehicle_asset(
            conn, company_id, customer_id, "WVWZZZ1JZ3W386752", created_at,
        )
    engine.dispose()

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0023_db)
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT customer_id, started_at, ended_at FROM asset_ownership "
            "WHERE asset_id = :asset_id"
        ), {"asset_id": asset_id}).one()
    engine.dispose()
    assert row.customer_id == customer_id
    assert row.ended_at is None
    assert row.started_at.replace(tzinfo=UTC) == created_at


def test_upgrade_through_0023_open_ownership_row_is_unique_per_asset(pre_0023_db: str) -> None:
    engine = create_engine(pre_0023_db)
    with engine.begin() as conn:
        company_id, customer_id = _seed_company_and_customer(
            conn, "Сервиз Преди 23Б", "pre23b@x.bg",
        )
        asset_id = _seed_vehicle_asset(
            conn, company_id, customer_id, "WAUZZZ8K9A123456", datetime.now(UTC),
        )
    engine.dispose()

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0023_db)
    with pytest.raises(IntegrityError, match="uq_asset_ownership_open"), engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO asset_ownership (id, company_id, asset_id, customer_id, started_at) "
            "VALUES (:id, :company_id, :asset_id, :customer_id, now())"
        ), {
            "id": uuid.uuid4(), "company_id": company_id, "asset_id": asset_id,
            "customer_id": customer_id,
        })
    engine.dispose()


def test_upgrade_through_0023_rejects_new_duplicate_vin_within_tenant(pre_0023_db: str) -> None:
    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(pre_0023_db)
    with engine.begin() as conn:
        company_id, customer_id = _seed_company_and_customer(conn, "Сервиз След 23", "post23@x.bg")
        _seed_vehicle_asset(conn, company_id, customer_id, "WVWZZZ1JZ3W386752", datetime.now(UTC))
    engine.dispose()

    engine = create_engine(pre_0023_db)
    with (
        pytest.raises(IntegrityError, match="uq_asset_identifiers_vin_company_value"),
        engine.begin() as conn,
    ):
        _seed_vehicle_asset(conn, company_id, customer_id, "WVWZZZ1JZ3W386752", datetime.now(UTC))
    engine.dispose()


def test_upgrade_through_0023_stops_on_pre_existing_duplicate_vins(pre_0023_db: str) -> None:
    """The migration must never auto-merge legacy duplicates — it stops with
    a clear, actionable error naming the conflicting rows instead."""
    engine = create_engine(pre_0023_db)
    with engine.begin() as conn:
        company_id, customer_id = _seed_company_and_customer(conn, "Сервиз Дубликат", "dup23@x.bg")
        _seed_vehicle_asset(conn, company_id, customer_id, "WVWZZZ1JZ3W386752", datetime.now(UTC))
        _seed_vehicle_asset(conn, company_id, customer_id, "WVWZZZ1JZ3W386752", datetime.now(UTC))
    engine.dispose()

    with pytest.raises(RuntimeError, match="duplicate normalized VINs"):
        command.upgrade(Config("alembic.ini"), "head")
