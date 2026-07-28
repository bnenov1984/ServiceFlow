"""Seat Limit editing (docs/business-os/18 §9 phase 5): a vendor-only,
audited mutation of `companies.seat_limit`. `companies.seat_limit` was read
for employee-seat enforcement since docs/business-os/18 §14.2, but until
this slice nothing ever wrote it — this file covers what is new: the setter
itself, its validation, and that it is always audited (closer in shape to
entitlement grant/revoke than to the reasoned subscription-transition
endpoint — no mandatory reason, no state machine).
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
TENANT_EMAIL = "maria@a.bg"
TENANT_PASSWORD = "парола-123"


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


def _seed_tenant() -> uuid.UUID:
    from business_os.identity.service import seed_company

    for db in _db():
        company = seed_company(db, "Сервиз А", "Мария", TENANT_EMAIL, TENANT_PASSWORD, "1234")
        return company.id
    raise AssertionError("unreachable")


def _vendor_login(client: TestClient) -> dict[str, object]:
    resp = client.post(f"{VENDOR}/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _tenant_login(client: TestClient) -> dict[str, object]:
    resp = client.post("/api/v1/auth/login",
                       json={"email": TENANT_EMAIL, "password": TENANT_PASSWORD})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _count_active_seats(company_id: uuid.UUID) -> int:
    from business_os.identity.service import count_active_seats

    for db in _db():
        return count_active_seats(db, company_id)  # type: ignore[arg-type]
    raise AssertionError("unreachable")


def _audit_actions() -> list[str]:
    from business_os.platform_admin.models import PlatformAuditLog

    for db in _db():
        return list(db.scalars(  # type: ignore[attr-defined]
            select(PlatformAuditLog.action).order_by(PlatformAuditLog.created_at)))
    raise AssertionError("unreachable")


def test_sets_a_seat_limit_and_records_the_change(client: TestClient) -> None:
    from business_os.platform_admin.models import PlatformAuditLog

    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.put(
        f"{VENDOR}/companies/{company_id}/seat-limit",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
        json={"seat_limit": 5},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["seat_limit"] == 5
    assert body["changed"] is True
    assert body["audit_id"]
    assert _audit_actions().count("company.seat_limit_changed") == 1

    for db in _db():
        row = db.get(PlatformAuditLog, uuid.UUID(body["audit_id"]))  # type: ignore[attr-defined]
        assert row is not None
        assert row.detail == {"from": None, "to": 5, "changed": True}


def test_setting_the_same_limit_again_is_still_audited_but_reports_unchanged(
    client: TestClient,
) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    client.put(f"{VENDOR}/companies/{company_id}/seat-limit", headers=headers,
              json={"seat_limit": 5})
    resp = client.put(f"{VENDOR}/companies/{company_id}/seat-limit", headers=headers,
                      json={"seat_limit": 5})

    assert resp.status_code == 200, resp.text
    assert resp.json()["changed"] is False
    assert _audit_actions().count("company.seat_limit_changed") == 2


def test_setting_null_after_a_numeric_limit_makes_it_unlimited(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    client.put(f"{VENDOR}/companies/{company_id}/seat-limit", headers=headers,
              json={"seat_limit": 3})
    resp = client.put(f"{VENDOR}/companies/{company_id}/seat-limit", headers=headers,
                      json={"seat_limit": None})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["seat_limit"] is None
    assert body["changed"] is True


@pytest.mark.parametrize("bad_limit", [0, -1])
def test_rejects_zero_and_negative_limits(client: TestClient, bad_limit: int) -> None:
    """Pydantic's `Field(gt=0)` violation is a schema-validation failure,
    surfaced as 400 `errors.validation` by the app's global
    `RequestValidationError` handler (serviceflow.main) — not a raw 422,
    consistent with every other Pydantic-rejected body in this app."""
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.put(
        f"{VENDOR}/companies/{company_id}/seat-limit",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
        json={"seat_limit": bad_limit},
    )
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_404s_for_a_nonexistent_company(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.put(
        f"{VENDOR}/companies/{uuid.uuid4()}/seat-limit",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
        json={"seat_limit": 5},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.provisioning.company_not_found"


def test_tenant_session_cannot_set_seat_limit(client: TestClient) -> None:
    company_id = _seed_tenant()
    me = _tenant_login(client)
    resp = client.put(
        f"{VENDOR}/companies/{company_id}/seat-limit",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
        json={"seat_limit": 5},
    )
    assert resp.status_code == 401


def test_requires_csrf(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    _vendor_login(client)
    resp = client.put(
        f"{VENDOR}/companies/{company_id}/seat-limit",
        json={"seat_limit": 5},
    )
    assert resp.status_code == 403


def test_setting_a_limit_below_current_usage_is_allowed(client: TestClient) -> None:
    """No retroactive check against current seat usage — lowering the limit
    below usage is a valid vendor action; enforcement remains entirely at the
    next employee create/reactivate call (identity.service.count_active_seats),
    unrelated to this slice."""
    from business_os.identity.models import User
    from business_os.identity.service import create_employee

    _reset_rate_limiter()
    company_id = _seed_tenant()  # seed_company creates one owner => 1 active seat
    _seed_admin()
    me = _vendor_login(client)

    for db in _db():
        owner = db.scalar(  # type: ignore[attr-defined]
            select(User).where(User.company_id == company_id, User.is_owner.is_(True)))
        assert owner is not None
        create_employee(db, company_id, owner.id, "Втори Служител",
                        "worker-a@dev-seed.bg", "парола-456")
        db.commit()  # type: ignore[attr-defined]
    assert _count_active_seats(company_id) == 2

    resp = client.put(
        f"{VENDOR}/companies/{company_id}/seat-limit",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
        json={"seat_limit": 1},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["seat_limit"] == 1
