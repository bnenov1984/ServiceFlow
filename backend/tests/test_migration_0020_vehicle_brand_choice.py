"""Migration #20 regression test (vehicle asset type's `brand` field becomes
a choice list, Issue 23 follow-up).

Same technique as test_migration_0018_tax_event_date.py: migrate to the
revision immediately before 0020, seed pre-migration state by hand (asset_types
rows in the OLD free-text-brand shape, the way a real pre-existing company's
data looks), continue to head, and verify the result — not model metadata
alone, the real upgrade path against a throwaway database.
"""

import json
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

OLD_VEHICLE_FIELD_DEFS = [
    {"key": "brand", "label_bg": "Марка", "type": "text"},
    {"key": "model", "label_bg": "Модел", "type": "text"},
    {"key": "reg_no", "label_bg": "Рег. №", "type": "text", "identifier_kind": "reg"},
    {"key": "vin", "label_bg": "VIN", "type": "text", "identifier_kind": "vin"},
    {"key": "year", "label_bg": "Година", "type": "number"},
    {"key": "mileage", "label_bg": "Пробег (км)", "type": "number"},
]

OLD_PHONE_FIELD_DEFS = [
    {"key": "brand", "label_bg": "Марка", "type": "text"},
    {"key": "model", "label_bg": "Модел", "type": "text"},
    {"key": "imei", "label_bg": "IMEI", "type": "text", "identifier_kind": "imei"},
]


@pytest.fixture
def pre_0020_db() -> Iterator[str]:
    """A throwaway database migrated only to revision 0019 — real
    pre-migration schema and data shape, before the brand field becomes a
    choice list."""
    base_url = os.environ["SERVICEFLOW_TEST_DATABASE_URL"]
    db_name = f"migration_0020_regression_{uuid.uuid4().hex[:12]}"
    admin_url = make_url(base_url).set(database="postgres")

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()

    test_url = make_url(base_url).set(database=db_name).render_as_string(hide_password=False)
    saved_env = os.environ.get("SERVICEFLOW_DATABASE_URL")
    os.environ["SERVICEFLOW_DATABASE_URL"] = test_url
    command.upgrade(Config("alembic.ini"), "0019")

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


def _seed_pre_migration_asset_types(url: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Two companies, each with the pre-0020 asset type set: `vehicle` (old
    free-text brand) and `phone` (brand is text too, but must stay untouched
    — only `vehicle`'s brand field changes). Returns
    (company_a_vehicle_id, company_a_phone_id, company_b_vehicle_id)."""
    engine = create_engine(url)
    company_a = uuid.uuid4()
    company_b = uuid.uuid4()
    vehicle_a = uuid.uuid4()
    phone_a = uuid.uuid4()
    vehicle_b = uuid.uuid4()

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO companies (id, name) VALUES (:id, 'Сервиз А'), (:id_b, 'Сервиз Б')"
        ), {"id": company_a, "id_b": company_b})
        conn.execute(text(
            "INSERT INTO asset_types (id, company_id, code, name_bg, business_profile, field_defs) "
            "VALUES (:id, :company_id, 'vehicle', 'Автомобил', 'generic_repair', "
            "CAST(:field_defs AS jsonb))"
        ), {"id": vehicle_a, "company_id": company_a,
            "field_defs": json.dumps(OLD_VEHICLE_FIELD_DEFS)})
        conn.execute(text(
            "INSERT INTO asset_types (id, company_id, code, name_bg, business_profile, field_defs) "
            "VALUES (:id, :company_id, 'phone', 'Телефон', 'generic_repair', "
            "CAST(:field_defs AS jsonb))"
        ), {"id": phone_a, "company_id": company_a,
            "field_defs": json.dumps(OLD_PHONE_FIELD_DEFS)})
        conn.execute(text(
            "INSERT INTO asset_types (id, company_id, code, name_bg, business_profile, field_defs) "
            "VALUES (:id, :company_id, 'vehicle', 'Автомобил', 'generic_repair', "
            "CAST(:field_defs AS jsonb))"
        ), {"id": vehicle_b, "company_id": company_b,
            "field_defs": json.dumps(OLD_VEHICLE_FIELD_DEFS)})

    engine.dispose()
    return vehicle_a, phone_a, vehicle_b


def _field_defs(url: str, asset_type_id: uuid.UUID) -> list[dict[str, object]]:
    engine = create_engine(url)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT field_defs FROM asset_types WHERE id = :id"), {"id": asset_type_id},
        ).one()
    engine.dispose()
    return list(row.field_defs)


def test_upgrade_through_0020_converts_existing_vehicle_brand_to_choice(
    pre_0020_db: str,
) -> None:
    vehicle_a, _phone_a, vehicle_b = _seed_pre_migration_asset_types(pre_0020_db)

    command.upgrade(Config("alembic.ini"), "head")

    defs = _field_defs(pre_0020_db, vehicle_a)
    brand = next(d for d in defs if d["key"] == "brand")
    assert brand["type"] == "choice"
    assert isinstance(brand["choices"], list)
    assert "Volkswagen" in brand["choices"]
    assert "Друго" in brand["choices"]
    assert brand["label_bg"] == "Марка"

    # Every company's vehicle asset type is backfilled, not just the first row.
    defs_b = _field_defs(pre_0020_db, vehicle_b)
    brand_b = next(d for d in defs_b if d["key"] == "brand")
    assert brand_b["type"] == "choice"


def test_upgrade_through_0020_leaves_every_other_field_untouched(pre_0020_db: str) -> None:
    vehicle_a, _phone_a, _vehicle_b = _seed_pre_migration_asset_types(pre_0020_db)

    command.upgrade(Config("alembic.ini"), "head")

    defs = _field_defs(pre_0020_db, vehicle_a)
    by_key = {d["key"]: d for d in defs}
    assert by_key["model"] == {"key": "model", "label_bg": "Модел", "type": "text"}
    assert by_key["reg_no"] == {
        "key": "reg_no", "label_bg": "Рег. №", "type": "text", "identifier_kind": "reg",
    }
    assert by_key["vin"] == {
        "key": "vin", "label_bg": "VIN", "type": "text", "identifier_kind": "vin",
    }
    assert by_key["year"] == {"key": "year", "label_bg": "Година", "type": "number"}
    assert by_key["mileage"] == {"key": "mileage", "label_bg": "Пробег (км)", "type": "number"}
    # Field order preserved (brand stays first) — the UI renders fields in
    # this array order.
    assert [d["key"] for d in defs] == ["brand", "model", "reg_no", "vin", "year", "mileage"]


def test_upgrade_through_0020_does_not_touch_other_asset_types(pre_0020_db: str) -> None:
    _vehicle_a, phone_a, _vehicle_b = _seed_pre_migration_asset_types(pre_0020_db)

    command.upgrade(Config("alembic.ini"), "head")

    assert _field_defs(pre_0020_db, phone_a) == OLD_PHONE_FIELD_DEFS
