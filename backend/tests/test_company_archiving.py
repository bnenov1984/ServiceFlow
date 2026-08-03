"""Company Archiving (docs/business-os/18 §9 phase 6): a vendor-only,
audited, logical/soft archive — never a delete. Covers what is new: the
archive/restore endpoints themselves, the company-list status filter, and
the two identity-side enforcement points (login rejection, live-session
lockout) that make an archive actually take effect without touching a
single user/session/subscription/business-data row.
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


def _seed_tenant(email: str = TENANT_EMAIL) -> uuid.UUID:
    from business_os.identity.service import seed_company

    for db in _db():
        company = seed_company(db, "Сервиз А", "Мария", email, TENANT_PASSWORD, "1234")
        return company.id
    raise AssertionError("unreachable")


def _vendor_login(client: TestClient) -> dict[str, object]:
    resp = client.post(f"{VENDOR}/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _tenant_login(client: TestClient, email: str = TENANT_EMAIL) -> dict[str, object]:
    resp = client.post("/api/v1/auth/login",
                       json={"email": email, "password": TENANT_PASSWORD})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _audit_actions() -> list[str]:
    from business_os.platform_admin.models import PlatformAuditLog

    for db in _db():
        return list(db.scalars(  # type: ignore[attr-defined]
            select(PlatformAuditLog.action).order_by(PlatformAuditLog.created_at)))
    raise AssertionError("unreachable")


def test_archives_a_company_and_records_the_change(client: TestClient) -> None:
    from business_os.platform_admin.models import PlatformAuditLog

    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.put(
        f"{VENDOR}/companies/{company_id}/archive",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["archived_at"] is not None
    assert body["changed"] is True
    assert body["audit_id"]
    assert _audit_actions().count("company.archived") == 1

    for db in _db():
        row = db.get(PlatformAuditLog, uuid.UUID(body["audit_id"]))  # type: ignore[attr-defined]
        assert row is not None
        assert row.detail == {"changed": True}


def test_archiving_an_already_archived_company_is_still_audited_but_unchanged(
    client: TestClient,
) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    client.put(f"{VENDOR}/companies/{company_id}/archive", headers=headers)
    resp = client.put(f"{VENDOR}/companies/{company_id}/archive", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["changed"] is False
    assert _audit_actions().count("company.archived") == 2


def test_restores_an_archived_company(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    client.put(f"{VENDOR}/companies/{company_id}/archive", headers=headers)
    resp = client.put(f"{VENDOR}/companies/{company_id}/restore", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["archived_at"] is None
    assert body["changed"] is True
    assert _audit_actions().count("company.restored") == 1


def test_restoring_an_already_active_company_is_still_audited_but_unchanged(
    client: TestClient,
) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    resp = client.put(f"{VENDOR}/companies/{company_id}/restore", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["changed"] is False
    assert _audit_actions().count("company.restored") == 1


def test_404s_for_a_nonexistent_company(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.put(
        f"{VENDOR}/companies/{uuid.uuid4()}/archive",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.provisioning.company_not_found"


def test_tenant_session_cannot_archive_a_company(client: TestClient) -> None:
    company_id = _seed_tenant()
    me = _tenant_login(client)
    resp = client.put(
        f"{VENDOR}/companies/{company_id}/archive",
        headers={"X-CSRF-Token": str(me["csrf_token"])},
    )
    assert resp.status_code == 401


def test_requires_csrf(client: TestClient) -> None:
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    _vendor_login(client)
    resp = client.put(f"{VENDOR}/companies/{company_id}/archive")
    assert resp.status_code == 403


def test_company_list_hides_archived_by_default(client: TestClient) -> None:
    _reset_rate_limiter()
    active_id = _seed_tenant("active-owner@a.bg")
    archived_id = _seed_tenant("archived-owner@a.bg")
    _seed_admin()
    me = _vendor_login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}
    client.put(f"{VENDOR}/companies/{archived_id}/archive", headers=headers)

    default_ids = {c["id"] for c in client.get(f"{VENDOR}/companies").json()}
    assert str(active_id) in default_ids
    assert str(archived_id) not in default_ids

    archived_only_ids = {c["id"] for c in client.get(f"{VENDOR}/companies?status=archived").json()}
    assert archived_only_ids == {str(archived_id)}

    all_ids = {c["id"] for c in client.get(f"{VENDOR}/companies?status=all").json()}
    assert all_ids == {str(active_id), str(archived_id)}


def test_archived_tenant_user_cannot_log_in(client: TestClient) -> None:
    """No distinct message — folds into the same generic rejection as a
    wrong password or a deactivated user (anti-enumeration)."""
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)
    client.put(f"{VENDOR}/companies/{company_id}/archive",
              headers={"X-CSRF-Token": str(me["csrf_token"])})

    resp = client.post("/api/v1/auth/login",
                       json={"email": TENANT_EMAIL, "password": TENANT_PASSWORD})
    assert resp.status_code == 401
    assert resp.json()["detail"]["message_key"] == "errors.auth.invalid_credentials"


def test_existing_session_stops_authorising_requests_once_archived(
    client: TestClient,
) -> None:
    """The critical proof: a session obtained *before* archiving must stop
    working on its very next request afterwards — no separate session
    revocation step, since resolve_session checks archived_at live."""
    _reset_rate_limiter()
    company_id = _seed_tenant()
    _tenant_login(client)
    assert client.get("/api/v1/auth/me").status_code == 200

    _seed_admin()
    me = _vendor_login(client)
    client.put(f"{VENDOR}/companies/{company_id}/archive",
              headers={"X-CSRF-Token": str(me["csrf_token"])})

    assert client.get("/api/v1/auth/me").status_code == 401


def test_archiving_deletes_nothing(client: TestClient) -> None:
    """Users, audit log rows and the company row itself all survive an
    archive untouched — only `archived_at` changes."""
    from business_os.identity.models import AuditLog, Company, User

    _reset_rate_limiter()
    company_id = _seed_tenant()
    _seed_admin()
    me = _vendor_login(client)

    for db in _db():
        users_before = len(list(db.scalars(  # type: ignore[attr-defined]
            select(User).where(User.company_id == company_id))))
        audit_before = len(list(db.scalars(  # type: ignore[attr-defined]
            select(AuditLog).where(AuditLog.company_id == company_id))))

    client.put(f"{VENDOR}/companies/{company_id}/archive",
              headers={"X-CSRF-Token": str(me["csrf_token"])})

    for db in _db():
        company = db.get(Company, company_id)  # type: ignore[attr-defined]
        assert company is not None
        assert company.archived_at is not None
        users_after = len(list(db.scalars(  # type: ignore[attr-defined]
            select(User).where(User.company_id == company_id))))
        audit_after = len(list(db.scalars(  # type: ignore[attr-defined]
            select(AuditLog).where(AuditLog.company_id == company_id))))
        assert users_after == users_before
        assert audit_after >= audit_before  # archiving itself adds no tenant-side audit row
