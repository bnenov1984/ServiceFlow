"""Migration #18 regression test (invoices.tax_event_date).

Drives the real upgrade/downgrade path against a throwaway database — not
model metadata alone — the same technique test_migration_0015 uses: migrate
to the revision immediately before 0018, seed pre-migration state by hand
(a company, order, and an invoice row inserted directly, the way a real
pre-migration deployment would have one), then continue to head and verify
the result. Much smaller in scope than 0015's test since this migration has
no backfill/data-transformation logic — a single nullable ADD COLUMN — so
the concern being verified is narrower: the exact column type, the absence
of a default, and that pre-existing rows survive with the new column NULL.
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
def pre_0018_db() -> Iterator[str]:
    """A throwaway database migrated only to revision 0017 — the real
    pre-migration schema, `invoices` included (migration 0009) but without
    `tax_event_date`."""
    base_url = os.environ["SERVICEFLOW_TEST_DATABASE_URL"]
    db_name = f"migration_0018_regression_{uuid.uuid4().hex[:12]}"
    admin_url = make_url(base_url).set(database="postgres")

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()

    test_url = make_url(base_url).set(database=db_name).render_as_string(hide_password=False)
    saved_env = os.environ.get("SERVICEFLOW_DATABASE_URL")
    os.environ["SERVICEFLOW_DATABASE_URL"] = test_url
    command.upgrade(Config("alembic.ini"), "0017")

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


def _seed_pre_migration_invoice(url: str) -> uuid.UUID:
    """A company, a user, a company-scoped asset type (post-migration-0015
    shape — `asset_types` is per-company, referenced by `assets.asset_type_id`,
    not the old global `asset_type_code`), a customer, an asset, an order, and
    one invoice row — inserted directly, the way a real pre-0018 deployment's
    existing data would look."""
    engine = create_engine(url)
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    asset_type_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    order_id = uuid.uuid4()
    invoice_id = uuid.uuid4()

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO companies (id, name) VALUES (:id, 'Сервиз Преди Миграция')"
        ), {"id": company_id})
        conn.execute(text(
            "INSERT INTO users (id, company_id, name, email, password_hash, is_owner) "
            "VALUES (:id, :company_id, 'Собственик', 'owner@pre18.bg', 'x', true)"
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
            "'Не се включва', 'received', :user_id)"
        ), {
            "id": order_id, "company_id": company_id, "customer_id": customer_id,
            "asset_id": asset_id, "user_id": user_id,
        })
        conn.execute(text(
            "INSERT INTO invoices (id, company_id, order_id, status) "
            "VALUES (:id, :company_id, :order_id, 'draft')"
        ), {"id": invoice_id, "company_id": company_id, "order_id": order_id})

    engine.dispose()
    return invoice_id


def test_upgrade_through_0018_adds_tax_event_date_as_nullable_date_column(
    pre_0018_db: str,
) -> None:
    invoice_id = _seed_pre_migration_invoice(pre_0018_db)

    command.upgrade(Config("alembic.ini"), "head")

    admin = create_engine(pre_0018_db)
    with admin.connect() as conn:
        column = conn.execute(text(
            "SELECT data_type, is_nullable, column_default FROM information_schema.columns "
            "WHERE table_name = 'invoices' AND column_name = 'tax_event_date'"
        )).one()
        assert column.data_type == "date"
        assert column.is_nullable == "YES"
        assert column.column_default is None

        # The pre-existing invoice row survives the migration with the new
        # column NULL — no backfill, no invented value.
        value = conn.execute(text(
            "SELECT tax_event_date FROM invoices WHERE id = :id"
        ), {"id": invoice_id}).scalar_one()
        assert value is None
    admin.dispose()


def test_downgrade_from_0018_removes_only_tax_event_date(pre_0018_db: str) -> None:
    _seed_pre_migration_invoice(pre_0018_db)
    command.upgrade(Config("alembic.ini"), "head")
    command.downgrade(Config("alembic.ini"), "0017")

    admin = create_engine(pre_0018_db)
    with admin.connect() as conn:
        columns = {
            row.column_name for row in conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'invoices'"
            ))
        }
        assert "tax_event_date" not in columns
        # Every other column from migration 0009 is still there, untouched.
        assert {
            "id", "company_id", "order_id", "status", "number", "issued_at",
            "seller", "buyer", "vat_mode", "net", "vat", "gross", "currency",
            "annuls_invoice_id", "annul_reason", "pdf_storage_key", "row_version",
        }.issubset(columns)
    admin.dispose()
