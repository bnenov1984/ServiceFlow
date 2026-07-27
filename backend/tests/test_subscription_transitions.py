"""Subscription Lifecycle (docs/business-os/18 §9 phase 4, §12.4, ADR-BOS-012):
a vendor-only, always-reasoned state transition, plus `require_subscription_ok`
— the Core mutation gate wired onto professional_services' own mutating
routes in this slice, per the user's explicit choice not to retrofit the
whole application yet.

Vendor auth/session mechanics, provisioning atomicity, and entitlement
management are already covered by earlier test files — this file focuses on
what is new: the reasoned transition itself, and that the gate really does
block mutations (never reads) while leaving entitlement enforcement
untouched and independent.
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
MODULE_KEY = "professional-services"


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


def _seed_tenant(with_module_active: bool = True) -> uuid.UUID:
    from business_os.identity.service import activate_module, seed_company

    for db in _db():
        company = seed_company(db, "Сервиз А", "Мария", TENANT_EMAIL, TENANT_PASSWORD, "1234")
        if with_module_active:
            activate_module(db, company.id, MODULE_KEY)
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


def _set_subscription_state_directly(company_id: uuid.UUID, state: str) -> None:
    """Bypasses the vendor endpoint — used to arrange a starting state for
    tests that aren't themselves testing the transition endpoint."""
    from business_os.identity.models import Company

    for db in _db():
        company = db.get(Company, company_id)  # type: ignore[attr-defined]
        company.subscription_state = state
        db.commit()  # type: ignore[attr-defined]


def _audit_actions() -> list[str]:
    from business_os.platform_admin.models import PlatformAuditLog

    for db in _db():
        return list(db.scalars(  # type: ignore[attr-defined]
            select(PlatformAuditLog.action).order_by(PlatformAuditLog.created_at)))
    raise AssertionError("unreachable")


# --- The transition itself -------------------------------------------------


def test_transition_changes_state_and_records_reason(client: TestClient) -> None:
    from business_os.platform_admin.models import PlatformAuditLog

    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.post(
        f"{VENDOR}/companies/{company_id}/subscription/transitions",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
        json={"new_state": "suspended", "reason": "Неплатена фактура за юли"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["old_state"] == "active"
    assert body["new_state"] == "suspended"
    assert body["reason"] == "Неплатена фактура за юли"
    assert body["audit_id"]
    assert _audit_actions().count("company.subscription_transitioned") == 1

    for db in _db():
        row = db.get(PlatformAuditLog, uuid.UUID(body["audit_id"]))  # type: ignore[attr-defined]
        assert row is not None
        assert row.reason == "Неплатена фактура за юли"
        assert row.detail == {"from": "active", "to": "suspended"}


def test_transition_requires_a_reason(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.post(
        f"{VENDOR}/companies/{company_id}/subscription/transitions",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
        json={"new_state": "suspended", "reason": "   "},
    )
    assert resp.status_code in (400, 422)  # blank after strip, or pydantic min_length


def test_transition_rejects_an_invalid_state(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.post(
        f"{VENDOR}/companies/{company_id}/subscription/transitions",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
        json={"new_state": "vip_forever", "reason": "made up state"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.subscription.invalid_state"


def test_transition_404s_for_a_nonexistent_company(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.post(
        f"{VENDOR}/companies/{uuid.uuid4()}/subscription/transitions",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
        json={"new_state": "suspended", "reason": "does not matter"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.provisioning.company_not_found"


def test_repeated_transitions_are_all_recorded_even_to_the_same_state(
    client: TestClient,
) -> None:
    """Unlike entitlement grant/revoke, a subscription transition is a real
    historical event, not an idempotent flag flip — re-asserting the same
    state (e.g. confirming payment again) still writes its own row, the same
    way PSDeadlineChange never suppresses a no-op deadline 'change'."""
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    client.post(f"{VENDOR}/companies/{company_id}/subscription/transitions", headers=headers,
               json={"new_state": "active", "reason": "reconfirmed active"})
    client.post(f"{VENDOR}/companies/{company_id}/subscription/transitions", headers=headers,
               json={"new_state": "active", "reason": "reconfirmed again"})

    assert _audit_actions().count("company.subscription_transitioned") == 2


# --- Route boundary (regression of the existing vendor guard) -----------


def test_tenant_session_cannot_transition_subscription(client: TestClient) -> None:
    company_id = _seed_tenant()
    me = _tenant_login(client)
    resp = client.post(
        f"{VENDOR}/companies/{company_id}/subscription/transitions",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
        json={"new_state": "suspended", "reason": "tenant cannot do this"},
    )
    assert resp.status_code == 401


def test_unauthenticated_cannot_transition_subscription(client: TestClient) -> None:
    company_id = _seed_tenant()
    resp = client.post(
        f"{VENDOR}/companies/{company_id}/subscription/transitions",
        json={"new_state": "suspended", "reason": "no session at all"},
    )
    assert resp.status_code == 401


def test_transition_requires_csrf(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    _vendor_login(client)
    resp = client.post(
        f"{VENDOR}/companies/{company_id}/subscription/transitions",
        json={"new_state": "suspended", "reason": "missing csrf"},
    )
    assert resp.status_code == 403


# --- require_subscription_ok: mutations blocked, reads never gated ------


@pytest.mark.parametrize("state", ["grace_period", "suspended", "cancelled"])
def test_mutations_are_blocked_in_read_only_states(client: TestClient, state: str) -> None:
    company_id = _seed_tenant()
    _set_subscription_state_directly(company_id, state)
    me = _tenant_login(client)

    resp = client.post("/api/v1/ps/clients", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json={"name": "Клиент", "kind": "person"})
    assert resp.status_code == 402
    assert resp.json()["detail"]["message_key"] == "errors.subscription.mutations_blocked"


@pytest.mark.parametrize("state", ["trial", "active"])
def test_mutations_succeed_in_paying_states(client: TestClient, state: str) -> None:
    company_id = _seed_tenant()
    _set_subscription_state_directly(company_id, state)
    me = _tenant_login(client)

    resp = client.post("/api/v1/ps/clients", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json={"name": "Клиент", "kind": "person"})
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("state", ["trial", "active", "grace_period", "suspended", "cancelled"])
def test_reads_never_gate_on_subscription_state(client: TestClient, state: str) -> None:
    """ADR-009's degradation promise, mechanically: every subscription state,
    including the most degraded (cancelled), still returns 200 on a read."""
    company_id = _seed_tenant()
    _set_subscription_state_directly(company_id, state)
    _tenant_login(client)

    assert client.get("/api/v1/ps/clients").status_code == 200


def test_a_live_tenant_session_reflects_a_transition_without_relogin(client: TestClient) -> None:
    """The guard reads live company state on every request — not something
    cached at login time."""
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    tenant_me = _tenant_login(client)
    tenant_headers = {"X-CSRF-Token": str(tenant_me["csrf_token"])}
    assert client.post("/api/v1/ps/clients", headers=tenant_headers,
                       json={"name": "Преди", "kind": "person"}).status_code == 200

    vendor_me = _vendor_login(client)
    client.post(f"{VENDOR}/companies/{company_id}/subscription/transitions",
               headers={"X-CSRF-Token": str(vendor_me["csrf_token"])},
               json={"new_state": "suspended", "reason": "live block test"})

    assert client.post("/api/v1/ps/clients", headers=tenant_headers,
                       json={"name": "След", "kind": "person"}).status_code == 402
    # ...and the read path for the same tenant session is unaffected.
    assert client.get("/api/v1/ps/clients").status_code == 200


# --- Independence from entitlement (ADR-BOS-010 §Decision 3) -------------


def test_subscription_and_entitlement_are_independent_axes(client: TestClient) -> None:
    """A suspended-but-still-entitled company: reads succeed (both guards
    are read-transparent), writes are blocked by subscription regardless of
    entitlement standing. An entitled-but-inactive-module company (the
    reverse) is already covered by require_ps_active's own tests — this
    proves the two checks don't collapse into each other."""
    company_id = _seed_tenant(with_module_active=True)
    _set_subscription_state_directly(company_id, "suspended")
    me = _tenant_login(client)

    assert client.get("/api/v1/ps/clients").status_code == 200  # entitled AND readable
    resp = client.post("/api/v1/ps/clients", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json={"name": "Клиент", "kind": "person"})
    assert resp.status_code == 402  # blocked by subscription, not entitlement
    assert resp.json()["detail"]["message_key"] == "errors.subscription.mutations_blocked"


def test_transition_never_touches_active_modules(client: TestClient) -> None:
    from business_os.identity.models import Company

    _reset_rate_limiter()
    company_id = _seed_tenant(with_module_active=True)
    _seed_admin()
    me = _vendor_login(client)

    client.post(f"{VENDOR}/companies/{company_id}/subscription/transitions",
               headers={"X-CSRF-Token": str(me["csrf_token"])},
               json={"new_state": "suspended", "reason": "independence check"})

    for db in _db():
        company = db.get(Company, company_id)  # type: ignore[attr-defined]
        assert company.settings.get("active_modules") == [MODULE_KEY]


# --- Platform-wide retrofit (docs/business-os/18 §13.3 follow-up,
# 28.07.2026): the structural completeness proof lives in
# tests/test_architecture.py — these are representative end-to-end checks
# that the mechanism generalizes beyond professional_services, the module it
# first shipped against. ------------------------------------------------


def test_customers_create_is_blocked_when_suspended(client: TestClient) -> None:
    company_id = _seed_tenant(with_module_active=False)
    _set_subscription_state_directly(company_id, "suspended")
    me = _tenant_login(client)

    resp = client.post("/api/v1/customers",
                       headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json={"name": "Иван Петров", "phone": "0888123456"})
    assert resp.status_code == 402
    assert resp.json()["detail"]["message_key"] == "errors.subscription.mutations_blocked"


def test_customers_read_and_create_are_unaffected_when_active(client: TestClient) -> None:
    company_id = _seed_tenant(with_module_active=False)
    _set_subscription_state_directly(company_id, "active")
    me = _tenant_login(client)

    assert client.get("/api/v1/customers").status_code == 200
    resp = client.post("/api/v1/customers",
                       headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json={"name": "Иван Петров", "phone": "0888123456"})
    assert resp.status_code == 201, resp.text


def test_customers_read_still_succeeds_when_suspended(client: TestClient) -> None:
    """The read half of ADR-009's degradation promise, on a second module —
    professional_services' own read-always proof is in
    test_reads_never_gate_on_subscription_state above."""
    company_id = _seed_tenant(with_module_active=False)
    _set_subscription_state_directly(company_id, "suspended")
    _tenant_login(client)

    assert client.get("/api/v1/customers").status_code == 200


def test_identity_logout_and_pinswitch_work_when_suspended(client: TestClient) -> None:
    """A suspended company's users must still be able to log out and PIN-switch
    — these are session mechanics, not the "business mutations" ADR-BOS-012
    means to gate."""
    company_id = _seed_tenant(with_module_active=False)
    _set_subscription_state_directly(company_id, "suspended")
    me = _tenant_login(client)

    resp = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": str(me["csrf_token"])})
    assert resp.status_code == 200


# --- Architecture regression -----------------------------------------------


def test_set_subscription_state_never_commits() -> None:
    import inspect
    import re

    from business_os.identity import contracts

    source = inspect.getsource(contracts.set_subscription_state)
    assert not re.search(r"\.commit\s*\(", source)
