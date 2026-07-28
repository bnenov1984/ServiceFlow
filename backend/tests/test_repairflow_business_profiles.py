"""RepairFlow Business Profiles — company-scoped asset_types (ADR-BOS-011
§Decision 5, docs/business-os/18 §15). Every company owns its own copy of
the asset-type set, seeded once at provisioning via the `company_provisioned`
domain event; the wire-level `asset_type_code` API contract is unchanged
(tests/test_assets.py, entirely unmodified by this slice, is the proof).

Per PO decision (28.07.2026): all five business profiles seed *identical*
content today — no per-profile field_defs exist yet. This file tests the
structural placeholder, not invented domain content.
"""

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)

VENDOR = "/api/v1/platform-admin"
ADMIN_EMAIL = "vendor.admin@business-os.bg"
ADMIN_PASSWORD = "вендор-парола-123"
EXPECTED_CODES = {"phone", "vehicle", "laptop", "other"}


def _db() -> Iterator[object]:
    from business_os.shared_kernel.db import open_session

    return open_session(os.environ["SERVICEFLOW_DATABASE_URL"])


def _reset_rate_limiter() -> None:
    from business_os.platform_admin import service

    service._failures.clear()  # noqa: SLF001


def _seed_admin() -> None:
    from business_os.platform_admin.service import create_platform_admin

    for db in _db():
        create_platform_admin(db, "Вендор Админ", ADMIN_EMAIL, ADMIN_PASSWORD)


def _vendor_login(client: TestClient) -> dict[str, object]:
    resp = client.post(f"{VENDOR}/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _provision(client: TestClient, business_profile: str, owner_email: str) -> uuid.UUID:
    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)
    resp = client.post(
        f"{VENDOR}/companies", headers={"X-CSRF-Token": str(me["csrf_token"])},
        json={
            "company_name": "Нов Сервиз ЕООД", "owner_name": "Иван Иванов",
            "owner_email": owner_email, "owner_password": "нова-парола-1234",
            "business_profile": business_profile,
        },
    )
    assert resp.status_code == 200, resp.text
    client.post(f"{VENDOR}/auth/logout", headers={"X-CSRF-Token": str(me["csrf_token"])})
    return uuid.UUID(resp.json()["company_id"])


def _tenant_login(client: TestClient, email: str,
                  password: str = "нова-парола-1234") -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _asset_types_for(company_id: uuid.UUID) -> list[object]:
    from business_os.identity.models import Company
    from business_os.shared_kernel.db import bind_tenant_scope
    from serviceflow.assets.models import AssetType

    for db in _db():
        bind_tenant_scope(db, company_id)  # type: ignore[arg-type]
        company = db.get(Company, company_id)  # type: ignore[attr-defined]
        assert company is not None
        return list(db.scalars(  # type: ignore[attr-defined]
            select(AssetType).where(AssetType.company_id == company_id)))
    raise AssertionError("unreachable")


# --- Seeding on provisioning ------------------------------------------------


def test_provision_company_seeds_four_asset_types(client: TestClient) -> None:
    company_id = _provision(client, "generic_repair", "owner1@shop.bg")
    types = _asset_types_for(company_id)
    assert {t.code for t in types} == EXPECTED_CODES
    assert all(t.business_profile == "generic_repair" for t in types)


@pytest.mark.parametrize("profile", [
    "generic_repair", "automotive_repair", "phone_repair",
    "electronics_repair", "appliance_repair",
])
def test_every_business_profile_seeds_identical_content(client: TestClient, profile: str) -> None:
    """Structural placeholder, confirmed: all five profiles produce the same
    codes/field_defs today — only the business_profile tag differs. Not a
    statement that this will always be true (docs/business-os/18 §15 is
    explicit that future profile-specific content is expected)."""
    company_id = _provision(client, profile, f"owner-{profile}@shop.bg")
    types = {t.code: t.field_defs for t in _asset_types_for(company_id)}
    generic_id = _provision(client, "generic_repair", f"owner-{profile}-ref@shop.bg")
    generic_types = {t.code: t.field_defs for t in _asset_types_for(generic_id)}
    assert types == generic_types


def test_seed_company_dev_path_also_seeds_asset_types(client: TestClient) -> None:
    """The dev/CLI path (identity.service.seed_company) must also publish
    company_provisioned — every company needs its own asset types, not only
    ones created through the Vendor Control Plane."""
    from business_os.identity.service import seed_company

    for db in _db():
        company = seed_company(db, "Директен сервиз", "Петър", "petar@direct.bg",
                               "парола-456", "1234")
        company_id = company.id

    types = _asset_types_for(company_id)
    assert {t.code for t in types} == EXPECTED_CODES
    assert all(t.business_profile == "generic_repair" for t in types)


# --- Wire contract unchanged, actually exercised end to end ----------------


def test_asset_creation_works_under_a_specialized_profile(client: TestClient) -> None:
    """Proves the seeded types are actually usable, not just present as
    rows — for a non-generic profile, since test_assets.py only ever
    exercises seed_company's generic_repair-tagged copy."""
    _provision(client, "automotive_repair", "owner2@shop.bg")
    me = _tenant_login(client, "owner2@shop.bg")
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    customer_id = client.post("/api/v1/customers", headers=headers,
                              json={"name": "Клиент", "phone": "0888000111"}).json()["id"]
    resp = client.post(f"/api/v1/customers/{customer_id}/assets", headers=headers, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "VW", "model": "Golf", "reg_no": "CA1234BT"},
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["asset_type_code"] == "vehicle"


def test_get_asset_types_is_scoped_per_company(client: TestClient) -> None:
    _provision(client, "generic_repair", "owner3@shop.bg")
    _tenant_login(client, "owner3@shop.bg")
    types = client.get("/api/v1/asset-types").json()
    assert {t["code"] for t in types} == EXPECTED_CODES


# --- Isolation ---------------------------------------------------------


def test_two_companies_get_independent_asset_type_rows(client: TestClient) -> None:
    """Not shared rows: each company owns 4 of its own, not a shared 4."""
    company_a = _provision(client, "generic_repair", "owner-a@shop.bg")
    company_b = _provision(client, "phone_repair", "owner-b@shop.bg")

    types_a = _asset_types_for(company_a)
    types_b = _asset_types_for(company_b)
    assert {t.id for t in types_a}.isdisjoint({t.id for t in types_b})
    assert len(types_a) == len(types_b) == 4


def test_rls_blocks_even_unscoped_asset_type_queries(client: TestClient) -> None:
    """ADR-016 layer 3: a raw query that forgets scoped()/the tenant
    dependency still cannot cross tenants — mirrors test_invoices.py's
    equivalent, applied to the newly-RLS'd asset_types."""
    from sqlalchemy import text

    from serviceflow.assets.models import AssetType

    _provision(client, "generic_repair", "owner4@shop.bg")

    for db in _db():
        assert db.scalars(select(AssetType)).all() == []  # type: ignore[attr-defined]
        db.execute(text(  # type: ignore[attr-defined]
            "SELECT set_config('app.company_id',"
            " '00000000-0000-0000-0000-000000000000', false)"
        ))
        assert db.scalars(select(AssetType)).all() == []  # type: ignore[attr-defined]


# --- Architecture regression -----------------------------------------------


def test_seed_default_types_never_commits() -> None:
    import inspect
    import re

    from serviceflow.assets import service

    source = inspect.getsource(service.seed_default_types)
    assert not re.search(r"\.commit\s*\(", source)
