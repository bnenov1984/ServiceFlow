"""Migration #15 regression test (asset_types becomes company-scoped).

Every other test in this repo migrates a *fresh, empty* database straight to
head and only seeds companies afterward — so a pre-existing company's global
`asset_types` row was never in the room when migration 0015 ran, and an
ordering bug went unnoticed: the per-company backfill INSERT ran while the
old bare-`code` primary key was still active, colliding with the still-
present original global rows on any database that already had a company
(`psycopg.errors.UniqueViolation` on `pk_asset_types`).

This test drives the *real* upgrade path instead: migrate a throwaway
database only to 0014 (the revision immediately before 0015), seed it by hand
the way a real pre-migration deployment would look (companies, a customer,
assets referencing the codes migration 0003 already seeded), then continue
through 0015 to head and verify the result — not a fresh-empty-database
shortcut.

Uses its own database (created and dropped per test), not the shared
session-scoped `migrated_db` fixture from conftest.py, which is already
migrated straight to head for the rest of the suite and would conflict with
downgrading/re-upgrading mid-session.
"""

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)

EXPECTED_CODES = {"phone", "vehicle", "laptop", "other"}


@pytest.fixture
def pre_0015_db() -> Iterator[str]:
    """A throwaway database migrated only to revision 0014 — the real
    pre-migration schema (companies, customers, assets, the four
    migration-0003-seeded global asset_types rows), not a hand-rolled
    approximation of it."""
    base_url = os.environ["SERVICEFLOW_TEST_DATABASE_URL"]
    db_name = f"migration_0015_regression_{uuid.uuid4().hex[:12]}"
    admin_url = make_url(base_url).set(database="postgres")

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()

    test_url = make_url(base_url).set(database=db_name).render_as_string(hide_password=False)
    saved_env = os.environ.get("SERVICEFLOW_DATABASE_URL")
    os.environ["SERVICEFLOW_DATABASE_URL"] = test_url
    command.upgrade(Config("alembic.ini"), "0014")

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


def _seed_pre_migration_state(url: str) -> dict[str, uuid.UUID]:
    """Two companies (one with a business_profile already assigned in
    `settings`, one without — the pre-provisioning-era shape,
    `identity.service.seed_company`'s own), a customer, and an asset
    referencing a pre-existing global code — exactly what the backfill has
    to reconcile."""
    engine = create_engine(url)
    company_a = uuid.uuid4()
    company_b = uuid.uuid4()
    customer_a = uuid.uuid4()
    asset_a = uuid.uuid4()

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO companies (id, name, settings) VALUES "
            "(:id, :name, CAST(:settings AS jsonb))"
        ), [
            {"id": company_a, "name": "Сервиз А",
             "settings": '{"repairflow": {"business_profile": "automotive_repair"}}'},
            {"id": company_b, "name": "Сервиз Б", "settings": "{}"},
        ])
        conn.execute(text(
            "INSERT INTO customers (id, company_id, name, phone, phone_normalized, "
            "name_translit) VALUES "
            "(:id, :company_id, 'Клиент А', '0888000111', '0888000111', 'Klient A')"
        ), {"id": customer_a, "company_id": company_a})
        # Referencing 'phone' — one of the four global rows migration 0003
        # already seeded on this database; not inserted again here.
        conn.execute(text(
            "INSERT INTO assets (id, company_id, customer_id, asset_type_code, label) "
            "VALUES (:id, :company_id, :customer_id, 'phone', 'iPhone 13')"
        ), {"id": asset_a, "company_id": company_a, "customer_id": customer_a})

    engine.dispose()
    return {"company_a": company_a, "company_b": company_b, "asset_a": asset_a}


def test_upgrade_through_0015_backfills_every_company_without_colliding(
    pre_0015_db: str,
) -> None:
    ids = _seed_pre_migration_state(pre_0015_db)

    # The actual regression: this used to raise psycopg.errors.UniqueViolation
    # ("duplicate key value violates unique constraint pk_asset_types") the
    # moment it hit company_a's backfill row, because company_a already
    # existed before 0015 ran — exactly the scenario every other test's
    # fresh-empty-database setup never exercised.
    command.upgrade(Config("alembic.ini"), "head")

    admin = create_engine(pre_0015_db)
    with admin.connect() as conn:
        # Each company got its own 4 rows, correctly tagged.
        rows_a = conn.execute(text(
            "SELECT code, business_profile FROM asset_types WHERE company_id = :cid"
        ), {"cid": ids["company_a"]}).all()
        rows_b = conn.execute(text(
            "SELECT code, business_profile FROM asset_types WHERE company_id = :cid"
        ), {"cid": ids["company_b"]}).all()

        assert {r.code for r in rows_a} == EXPECTED_CODES
        assert {r.code for r in rows_b} == EXPECTED_CODES
        assert all(r.business_profile == "automotive_repair" for r in rows_a), rows_a
        assert all(r.business_profile == "generic_repair" for r in rows_b), rows_b

        # No leftover global rows.
        assert conn.execute(text(
            "SELECT count(*) FROM asset_types WHERE company_id IS NULL"
        )).scalar_one() == 0

        # Existing asset reference still resolves — and to *its own*
        # company's row, not some other company's same-code row.
        asset_type_id, resolved_company_id = conn.execute(text(
            "SELECT asset_type_id, (SELECT company_id FROM asset_types "
            "WHERE id = a.asset_type_id) FROM assets a WHERE a.id = :aid"
        ), {"aid": ids["asset_a"]}).one()
        assert asset_type_id is not None
        assert resolved_company_id == ids["company_a"]

        code = conn.execute(text(
            "SELECT code FROM asset_types WHERE id = :id"
        ), {"id": asset_type_id}).scalar_one()
        assert code == "phone"
    admin.dispose()


def test_unique_company_id_code_is_actually_enforced(pre_0015_db: str) -> None:
    ids = _seed_pre_migration_state(pre_0015_db)
    command.upgrade(Config("alembic.ini"), "head")

    admin = create_engine(pre_0015_db)
    with admin.begin() as conn, pytest.raises(
        IntegrityError, match="uq_asset_types_company_id_code",
    ):
        conn.execute(text(
            "INSERT INTO asset_types (id, company_id, code, name_bg, icon, sort, "
            "field_defs, business_profile) VALUES "
            "(gen_random_uuid(), :cid, 'phone', 'Дубликат', '', 0, '[]'::jsonb, "
            "'generic_repair')"
        ), {"cid": ids["company_a"]})
    admin.dispose()


def test_rls_scopes_asset_types_per_company_after_migration(pre_0015_db: str) -> None:
    from business_os.shared_kernel.db import bind_tenant_scope, open_session

    ids = _seed_pre_migration_state(pre_0015_db)
    command.upgrade(Config("alembic.ini"), "head")

    admin_engine = create_engine(pre_0015_db, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(
            "DO $$ BEGIN IF NOT EXISTS "
            "(SELECT FROM pg_roles WHERE rolname = 'sf_app') THEN "
            "CREATE ROLE sf_app LOGIN PASSWORD 'sf-app-pw'; END IF; END $$"
        ))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO sf_app"))
        conn.execute(text(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sf_app"
        ))
    admin_engine.dispose()

    app_url = (
        make_url(pre_0015_db).set(username="sf_app", password="sf-app-pw")
        .render_as_string(hide_password=False)
    )

    from sqlalchemy import select

    from serviceflow.assets.models import AssetType

    for db in open_session(app_url):
        bind_tenant_scope(db, ids["company_a"])  # type: ignore[arg-type]
        seen = db.scalars(select(AssetType)).all()  # type: ignore[attr-defined]
        assert {t.code for t in seen} == EXPECTED_CODES
        assert all(t.company_id == ids["company_a"] for t in seen)

    for db in open_session(app_url):
        bind_tenant_scope(db, ids["company_b"])  # type: ignore[arg-type]
        seen = db.scalars(select(AssetType)).all()  # type: ignore[attr-defined]
        assert {t.code for t in seen} == EXPECTED_CODES
        assert all(t.company_id == ids["company_b"] for t in seen)

    # Fail-closed: no tenant scope bound at all → zero rows, not an error and
    # not every company's rows (ADR-016 layer 3).
    for db in open_session(app_url):
        seen = db.scalars(select(AssetType)).all()  # type: ignore[attr-defined]
        assert seen == []
