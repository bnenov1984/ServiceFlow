"""RepairFlow as a real entitlement (PO decision, 01.08.2026): no application
is active by default at provisioning — the vendor must explicitly grant at
least one of {"repairflow", "professional-services"}, and `require_
repairflow_active` (mirroring `professional_services.deps.require_ps_active`)
now gates every RepairFlow domain router the same way PropertyFlow's own
router already was gated. This file covers what is new: the guard itself,
the provisioning restriction, and that platform/auth/tenant-admin routes
stay reachable regardless of RepairFlow entitlement. Migration 0016's
backfill (existing companies keep working) is covered separately, at the
bottom, using the pre/post-upgrade technique
`test_migration_0015_asset_types_backfill.py` established.
"""

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)

VENDOR = "/api/v1/platform-admin"
ADMIN_EMAIL = "vendor.admin@business-os.bg"
ADMIN_PASSWORD = "вендор-парола-123"


def _db() -> Iterator[object]:
    from business_os.shared_kernel.db import open_session

    return open_session(os.environ["SERVICEFLOW_DATABASE_URL"])


def _reset_rate_limiter() -> None:
    from business_os.platform_admin import service

    service._failures.clear()  # noqa: SLF001


def _seed_admin() -> uuid.UUID:
    from business_os.platform_admin.service import create_platform_admin

    for db in _db():
        admin, _ = create_platform_admin(db, "Вендор Админ", ADMIN_EMAIL, ADMIN_PASSWORD)
        return admin.id
    raise AssertionError("unreachable")


def _vendor_login(client: TestClient) -> dict[str, object]:
    resp = client.post(f"{VENDOR}/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _provision(client: TestClient, csrf: str, modules: list[str],
               email: str) -> dict[str, object]:
    resp = client.post(
        f"{VENDOR}/companies",
        headers={"X-CSRF-Token": csrf},
        json={
            "company_name": "Тест ЕООД", "owner_name": "Собственик",
            "owner_email": email, "owner_password": "парола-1234567",
            "business_profile": "generic_repair",
            "business_type_label": "Тестова дейност", "modules": modules,
        },
    )
    return {"status": resp.status_code, "body": resp.json()}


def _tenant_login(client: TestClient, email: str) -> dict[str, object]:
    resp = client.post("/api/v1/auth/login",
                       json={"email": email, "password": "парола-1234567"})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def test_repairflow_only_can_use_repairflow_but_not_propertyflow(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    vendor_me = _vendor_login(client)
    result = _provision(client, str(vendor_me["csrf_token"]), ["repairflow"],
                        "owner.rf@test.bg")
    assert result["status"] == 200, result["body"]

    tenant_me = _tenant_login(client, "owner.rf@test.bg")
    headers = {"X-CSRF-Token": str(tenant_me["csrf_token"])}

    assert client.get("/api/v1/customers").status_code == 200
    ps_resp = client.get("/api/v1/ps/clients", headers=headers)
    assert ps_resp.status_code == 404
    assert ps_resp.json()["detail"]["message_key"] == "errors.ps.module_inactive"


def test_propertyflow_only_can_use_propertyflow_but_not_repairflow(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    vendor_me = _vendor_login(client)
    result = _provision(client, str(vendor_me["csrf_token"]), ["professional-services"],
                        "owner.ps@test.bg")
    assert result["status"] == 200, result["body"]

    tenant_me = _tenant_login(client, "owner.ps@test.bg")
    headers = {"X-CSRF-Token": str(tenant_me["csrf_token"])}

    assert client.get("/api/v1/ps/clients", headers=headers).status_code == 200
    rf_resp = client.get("/api/v1/customers")
    assert rf_resp.status_code == 404
    assert rf_resp.json()["detail"]["message_key"] == "errors.repairflow.module_inactive"


def test_selecting_both_at_provisioning_is_rejected(client: TestClient) -> None:
    """One application per company (PO decision, 11.09.2026) — RepairFlow and
    PropertyFlow are mutually exclusive, so provisioning with both selected
    must fail before any company/owner is created, the same posture as the
    empty-selection case just above."""
    _reset_rate_limiter()
    _seed_admin()
    vendor_me = _vendor_login(client)
    result = _provision(client, str(vendor_me["csrf_token"]),
                        ["repairflow", "professional-services"], "owner.both@test.bg")

    assert result["status"] == 400, result["body"]
    body = result["body"]
    assert isinstance(body, dict)
    assert body["detail"]["message_key"] == "errors.provisioning.multiple_modules_not_allowed"
    assert client.post("/api/v1/auth/login", json={
        "email": "owner.both@test.bg", "password": "парола-1234567",
    }).status_code == 401


def test_provisioning_with_no_modules_is_rejected(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    vendor_me = _vendor_login(client)
    result = _provision(client, str(vendor_me["csrf_token"]), [], "owner.none@test.bg")

    assert result["status"] == 400, result["body"]
    body = result["body"]
    assert isinstance(body, dict)
    assert body["detail"]["message_key"] == "errors.provisioning.no_modules_selected"
    # No company/owner was created — the rejected email can be reused.
    assert client.post("/api/v1/auth/login", json={
        "email": "owner.none@test.bg", "password": "парола-1234567",
    }).status_code == 401


def test_platform_and_auth_routes_work_regardless_of_repairflow_entitlement(
    client: TestClient,
) -> None:
    _reset_rate_limiter()
    _seed_admin()
    vendor_me = _vendor_login(client)
    result = _provision(client, str(vendor_me["csrf_token"]), ["professional-services"],
                        "owner.platform@test.bg")
    assert result["status"] == 200, result["body"]

    tenant_me = _tenant_login(client, "owner.platform@test.bg")
    headers = {"X-CSRF-Token": str(tenant_me["csrf_token"])}

    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.get("/api/v1/users").status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200


# --- Migration 0016 backfill (mirrors test_migration_0015's own technique) -


@pytest.fixture
def pre_0016_db() -> Iterator[str]:
    """A throwaway database migrated only to revision 0015 — before
    RepairFlow's entitlement guard and its backfill migration existed."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    base_url = os.environ["SERVICEFLOW_TEST_DATABASE_URL"]
    db_name = f"migration_0016_regression_{uuid.uuid4().hex[:12]}"
    admin_url = make_url(base_url).set(database="postgres")

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()

    test_url = make_url(base_url).set(database=db_name).render_as_string(hide_password=False)
    saved_env = os.environ.get("SERVICEFLOW_DATABASE_URL")
    os.environ["SERVICEFLOW_DATABASE_URL"] = test_url
    command.upgrade(Config("alembic.ini"), "0015")

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


def test_migration_0016_backfills_repairflow_for_pre_existing_companies(
    pre_0016_db: str,
) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    engine = create_engine(pre_0016_db)
    company_no_modules = uuid.uuid4()
    company_with_ps = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO companies (id, name, settings) VALUES "
            "(:id, 'Сервиз А', '{}'::jsonb)"
        ), {"id": company_no_modules})
        conn.execute(text(
            "INSERT INTO companies (id, name, settings) VALUES "
            "(:id, 'Сервиз Б', CAST(:settings AS jsonb))"
        ), {"id": company_with_ps,
            "settings": '{"active_modules": ["professional-services"]}'})
    engine.dispose()

    command.upgrade(Config("alembic.ini"), "head")

    admin = create_engine(pre_0016_db)
    with admin.connect() as conn:
        modules_a = conn.execute(text(
            "SELECT settings -> 'active_modules' FROM companies WHERE id = :id"
        ), {"id": company_no_modules}).scalar_one()
        modules_b = conn.execute(text(
            "SELECT settings -> 'active_modules' FROM companies WHERE id = :id"
        ), {"id": company_with_ps}).scalar_one()
    admin.dispose()

    assert modules_a == ["repairflow"]
    assert set(modules_b) == {"professional-services", "repairflow"}
