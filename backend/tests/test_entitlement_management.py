"""Entitlement Management (docs/business-os/18 §9 phase 3, ADR-BOS-010):
grant/revoke one module entitlement for an existing company, its own atomic
vendor operation (existence check, mutation, one audit row, one commit),
symmetric to Company Provisioning's initial grant.

Vendor auth/session mechanics, provisioning atomicity, and the metadata-only
read surface are already covered by tests/test_vendor_security.py and
tests/test_company_provisioning.py — this file focuses on what is new:
grant/revoke idempotency, the audit trail, and — the strongest proof this
slice actually works — that flipping the entitlement here really does
change what a tenant session can reach through `require_ps_active`.
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


def _seed_tenant() -> uuid.UUID:
    """A plain seed_company company starts with only `"repairflow"` active
    (granted unconditionally since the 01.08.2026 PO decision — a dev/staging
    seed's whole purpose is a working RepairFlow demo tenant) — never
    `professional-services`. That's what makes this file's grant/revoke
    assertions for `MODULE_KEY` observable from a known cold start; every
    assertion below accounts for `"repairflow"` already being present."""
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


def _audit_actions() -> list[str]:
    from business_os.platform_admin.models import PlatformAuditLog

    for db in _db():
        return list(db.scalars(  # type: ignore[attr-defined]
            select(PlatformAuditLog.action).order_by(PlatformAuditLog.created_at)))
    raise AssertionError("unreachable")


# --- Grant / revoke, idempotency ------------------------------------------


def test_grant_activates_the_module(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.put(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}",
                      headers={"X-CSRF-Token": str(me["csrf_token"])})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["company_id"] == str(company_id)
    assert body["module_key"] == MODULE_KEY
    assert set(body["active_modules"]) == {"repairflow", MODULE_KEY}
    assert body["changed"] is True
    assert body["audit_id"]
    assert _audit_actions().count("company.module_granted") == 1


def test_granting_an_already_active_module_is_idempotent(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    first = client.put(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}", headers=headers)
    assert first.json()["changed"] is True

    second = client.put(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}", headers=headers)
    assert second.status_code == 200
    assert second.json()["changed"] is False
    assert set(second.json()["active_modules"]) == {"repairflow", MODULE_KEY}  # not duplicated

    # Idempotent does not mean unaudited — a vendor action attempted is still
    # worth a record, even as a no-op.
    assert _audit_actions().count("company.module_granted") == 2


def test_revoke_deactivates_the_module(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}
    client.put(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}", headers=headers)

    resp = client.delete(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["active_modules"] == ["repairflow"]
    assert body["changed"] is True
    assert _audit_actions().count("company.module_revoked") == 1


def test_revoking_an_already_inactive_module_is_idempotent(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    resp = client.delete(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["changed"] is False
    assert resp.json()["active_modules"] == ["repairflow"]
    assert _audit_actions().count("company.module_revoked") == 1


def test_grant_and_revoke_are_scoped_to_the_named_module_only(client: TestClient) -> None:
    """Granting one module must not disturb another already-active one."""
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    client.put(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}", headers=headers)
    resp = client.put(f"{VENDOR}/companies/{company_id}/modules/another-module", headers=headers)
    assert set(resp.json()["active_modules"]) == {"repairflow", MODULE_KEY, "another-module"}

    resp = client.delete(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}",
                         headers=headers)
    assert set(resp.json()["active_modules"]) == {"repairflow", "another-module"}


# --- Existence check -------------------------------------------------------


def test_grant_404s_for_a_nonexistent_company(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.put(f"{VENDOR}/companies/{uuid.uuid4()}/modules/{MODULE_KEY}",
                      headers={"X-CSRF-Token": str(me["csrf_token"])})
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.provisioning.company_not_found"
    # No audit row for an operation that never found its target — only the
    # bootstrap/login rows _seed_admin()/_vendor_login() already wrote.
    assert "company.module_granted" not in _audit_actions()


def test_revoke_404s_for_a_nonexistent_company(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.delete(f"{VENDOR}/companies/{uuid.uuid4()}/modules/{MODULE_KEY}",
                         headers={"X-CSRF-Token": str(me["csrf_token"])})
    assert resp.status_code == 404
    assert "company.module_revoked" not in _audit_actions()


# --- Route boundary (regression of the existing vendor guard) -----------


def test_tenant_session_cannot_grant_or_revoke(client: TestClient) -> None:
    company_id = _seed_tenant()
    me = _tenant_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    assert client.put(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}",
                      headers=headers).status_code == 401
    assert client.delete(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}",
                         headers=headers).status_code == 401


def test_unauthenticated_cannot_grant_or_revoke(client: TestClient) -> None:
    company_id = _seed_tenant()
    assert client.put(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}"
                      ).status_code == 401
    assert client.delete(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}"
                         ).status_code == 401


def test_grant_and_revoke_require_csrf(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    _vendor_login(client)

    assert client.put(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}"
                      ).status_code == 403
    assert client.delete(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}"
                         ).status_code == 403


# --- Independence from subscription state (ADR-BOS-010 §Decision 3) ------


def test_entitlement_change_never_touches_subscription_state(client: TestClient) -> None:
    from business_os.identity.models import Company

    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    for db in _db():
        before = db.get(Company, company_id)  # type: ignore[attr-defined]
        before_state = before.subscription_state
        before_changed_at = before.subscription_state_changed_at
        before_trial = before.trial_ends_at

    client.put(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}", headers=headers)
    client.delete(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}", headers=headers)

    for db in _db():
        after = db.get(Company, company_id)  # type: ignore[attr-defined]
        assert after.subscription_state == before_state
        assert after.subscription_state_changed_at == before_changed_at
        assert after.trial_ends_at == before_trial


# --- The real proof: require_ps_active actually respects the flag --------


def test_granting_and_revoking_actually_changes_what_the_tenant_can_reach(
    client: TestClient,
) -> None:
    """End-to-end, not a storage-layer assertion: before any grant, the
    tenant's own professional-services route 404s (require_ps_active,
    unchanged by this slice); after the vendor grants the module, the same
    route succeeds; after the vendor revokes it, it 404s again. This is what
    ADR-BOS-010 §Decision 5 means by "the audited endpoint the console must
    call" actually mattering — not just a JSONB key changing in isolation."""
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()

    _tenant_login(client)
    assert client.get("/api/v1/ps/clients").status_code == 404

    vendor_me = _vendor_login(client)
    vendor_headers = {"X-CSRF-Token": str(vendor_me["csrf_token"])}
    client.put(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}", headers=vendor_headers)

    # Same tenant session as before — no re-login, proving the guard reads
    # live company state, not something cached at login time.
    assert client.get("/api/v1/ps/clients").status_code == 200

    client.delete(f"{VENDOR}/companies/{company_id}/modules/{MODULE_KEY}", headers=vendor_headers)
    assert client.get("/api/v1/ps/clients").status_code == 404


# --- Architecture regression -----------------------------------------------


def test_entitlement_functions_never_commit_except_once() -> None:
    """grant_entitlement/revoke_entitlement own a single commit boundary,
    same discipline as provision_company — a future edit that slips an
    extra commit into identity.contracts.grant_module/revoke_module would
    break the "existence check, mutation and audit land together" guarantee."""
    import inspect
    import re

    from business_os.identity import contracts

    for name in ("grant_module", "revoke_module"):
        source = inspect.getsource(getattr(contracts, name))
        assert not re.search(r"\.commit\s*\(", source), (
            f"identity.contracts.{name} appears to call .commit()"
        )
