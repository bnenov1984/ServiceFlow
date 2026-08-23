"""Tenant Employee Management + Seat Limits (docs/13 Étап 3,
docs/business-os/18 §9 phase 7): Owner-only create/activate/deactivate/role
management, bounded by the vendor-set seat limit.

    Tenant Owner creates/reactivates employee
                    ↓
             count active seats
                    ↓
            compare with seat_limit
                    ↓
              allow or reject

No new table, no new migration — `users`/`companies.seat_limit` already
exist; every mutation writes to the existing tenant `audit_log`.
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

OWNER_EMAIL = "maria@a.bg"
OWNER_PASSWORD = "парола-123"


def _db() -> Iterator[object]:
    from business_os.shared_kernel.db import open_session

    return open_session(os.environ["SERVICEFLOW_DATABASE_URL"])


def _seed_owner() -> uuid.UUID:
    from business_os.identity.service import seed_company

    for db in _db():
        company = seed_company(db, "Сервиз А", "Мария", OWNER_EMAIL, OWNER_PASSWORD, "1234")
        return company.id
    raise AssertionError("unreachable")


def _login(client: TestClient, email: str = OWNER_EMAIL,
          password: str = OWNER_PASSWORD) -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _set_seat_limit(company_id: uuid.UUID, limit: int | None) -> None:
    from business_os.identity.models import Company

    for db in _db():
        company = db.get(Company, company_id)  # type: ignore[attr-defined]
        company.seat_limit = limit
        db.commit()  # type: ignore[attr-defined]


def _set_subscription_state(company_id: uuid.UUID, state: str) -> None:
    from business_os.identity.models import Company

    for db in _db():
        company = db.get(Company, company_id)  # type: ignore[attr-defined]
        company.subscription_state = state
        db.commit()  # type: ignore[attr-defined]


def _audit_actions(company_id: uuid.UUID) -> list[str]:
    from business_os.identity.models import AuditLog

    for db in _db():
        return list(db.scalars(  # type: ignore[attr-defined]
            select(AuditLog.action).where(AuditLog.company_id == company_id)
            .order_by(AuditLog.created_at)))
    raise AssertionError("unreachable")


def _employee_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Иво Иванов", "email": "ivo@a.bg", "password": "парола-за-иво-123",
    }
    payload.update(overrides)
    return payload


# --- Create ---------------------------------------------------------------


def test_owner_can_create_a_worker(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)

    resp = client.post("/api/v1/users", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json=_employee_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Иво Иванов"
    assert body["email"] == "ivo@a.bg"
    assert body["is_owner"] is False
    assert body["is_active"] is True

    listing = client.get("/api/v1/users").json()
    assert {u["email"] for u in listing} == {OWNER_EMAIL, "ivo@a.bg"}


def test_owner_can_create_a_co_owner(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)

    resp = client.post("/api/v1/users", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json=_employee_payload(is_owner=True))
    assert resp.status_code == 201
    assert resp.json()["is_owner"] is True


def test_worker_cannot_create_an_employee(client: TestClient) -> None:
    _seed_owner()
    owner_me = _login(client)
    client.post("/api/v1/users", headers={"X-CSRF-Token": str(owner_me["csrf_token"])},
               json=_employee_payload())
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": str(owner_me["csrf_token"])})

    worker_me = _login(client, email="ivo@a.bg", password="парола-за-иво-123")
    resp = client.post("/api/v1/users", headers={"X-CSRF-Token": str(worker_me["csrf_token"])},
                       json=_employee_payload(email="trети@a.bg"))
    assert resp.status_code == 403


def test_create_employee_requires_csrf(client: TestClient) -> None:
    _seed_owner()
    _login(client)
    resp = client.post("/api/v1/users", json=_employee_payload())
    assert resp.status_code == 403


def test_create_employee_rejects_duplicate_email(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    resp = client.post("/api/v1/users", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json=_employee_payload(email=OWNER_EMAIL))
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.employees.email_taken"


# --- Seat usage / seat limit -----------------------------------------------


def test_seat_usage_reflected_on_me(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    assert me["seat_usage"] == 1
    assert me["seat_limit"] is None

    client.post("/api/v1/users", headers={"X-CSRF-Token": str(me["csrf_token"])},
               json=_employee_payload())
    assert client.get("/api/v1/auth/me").json()["seat_usage"] == 2


def test_seat_limit_null_means_unlimited(client: TestClient) -> None:
    company_id = _seed_owner()
    _set_seat_limit(company_id, None)
    me = _login(client)

    for i in range(5):
        resp = client.post("/api/v1/users", headers={"X-CSRF-Token": str(me["csrf_token"])},
                           json=_employee_payload(email=f"worker{i}@a.bg"))
        assert resp.status_code == 201, resp.text


def test_seat_limit_blocks_create_once_reached(client: TestClient) -> None:
    company_id = _seed_owner()
    _set_seat_limit(company_id, 2)  # owner + 1 worker
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    assert client.post("/api/v1/users", headers=headers,
                       json=_employee_payload()).status_code == 201
    resp = client.post("/api/v1/users", headers=headers,
                       json=_employee_payload(email="втори@a.bg"))
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.employees.seat_limit_reached"


def test_seat_limit_blocks_reactivation_when_at_capacity(client: TestClient) -> None:
    """Reactivating a previously-deactivated employee must count against the
    limit exactly like creating a new one."""
    company_id = _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}
    created = client.post("/api/v1/users", headers=headers,
                          json=_employee_payload()).json()

    # Deactivate, then fill the now-freed seat with someone else.
    client.patch(f"/api/v1/users/{created['id']}", headers=headers, json={"is_active": False})
    client.post("/api/v1/users", headers=headers,
               json=_employee_payload(email="втори@a.bg"))
    _set_seat_limit(company_id, 2)  # owner + втори — exactly at capacity now

    resp = client.patch(f"/api/v1/users/{created['id']}", headers=headers,
                        json={"is_active": True})
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.employees.seat_limit_reached"


# --- Activate / deactivate / role change -----------------------------------


def test_deactivate_and_reactivate_employee(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}
    created = client.post("/api/v1/users", headers=headers,
                          json=_employee_payload()).json()

    resp = client.patch(f"/api/v1/users/{created['id']}", headers=headers,
                        json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    assert "ivo@a.bg" not in {u["email"] for u in client.get("/api/v1/users").json()}
    assert "ivo@a.bg" in {
        u["email"] for u in client.get("/api/v1/users?include_inactive=true").json()
    }

    resp = client.patch(f"/api/v1/users/{created['id']}", headers=headers,
                        json={"is_active": True})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

def test_deactivated_employee_existing_session_becomes_invalid(
    client: TestClient,
) -> None:
    from serviceflow.main import create_app

    _seed_owner()

    # Owner session
    owner_me = _login(client)
    owner_headers = {"X-CSRF-Token": str(owner_me["csrf_token"])}

    create_resp = client.post(
        "/api/v1/users",
        headers=owner_headers,
        json=_employee_payload(),
)
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()

    # Separate Worker session — simulates another browser/device.
    with TestClient(create_app()) as worker_client:
        worker_me = _login(
            worker_client,
            email="ivo@a.bg",
            password="парола-за-иво-123",
        )

        assert worker_me["email"] == "ivo@a.bg"
        assert worker_client.get("/api/v1/auth/me").status_code == 200

        # Owner deactivates the worker while worker's session already exists.
        resp = client.patch(
            f"/api/v1/users/{created['id']}",
            headers=owner_headers,
            json={"is_active": False},
        )
        assert resp.status_code == 200

        # The original Worker cookie/session must no longer authorize requests.
        resp = worker_client.get("/api/v1/auth/me")
        assert resp.status_code == 401


def test_promote_worker_to_owner(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}
    created = client.post("/api/v1/users", headers=headers,
                          json=_employee_payload()).json()
    assert created["is_owner"] is False

    resp = client.patch(f"/api/v1/users/{created['id']}", headers=headers,
                        json={"is_owner": True})
    assert resp.status_code == 200
    assert resp.json()["is_owner"] is True


def test_update_employee_404s_for_a_nonexistent_id(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    resp = client.patch(f"/api/v1/users/{uuid.uuid4()}",
                        headers={"X-CSRF-Token": str(me["csrf_token"])},
                        json={"is_active": False})
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.employees.not_found"


def test_update_employee_404s_for_a_different_companys_employee(client: TestClient) -> None:
    from business_os.identity.models import User
    from business_os.identity.service import seed_company

    _seed_owner()
    for db in _db():
        seed_company(db, "Сервиз Б", "Петър", "petar@b.bg", "парола-456", "9999")
        other_owner = db.scalar(select(User).where(User.email == "petar@b.bg"))  # type: ignore[attr-defined]
        other_owner_id = str(other_owner.id)
    me = _login(client)

    resp = client.patch(f"/api/v1/users/{other_owner_id}",
                        headers={"X-CSRF-Token": str(me["csrf_token"])},
                        json={"is_active": False})
    assert resp.status_code == 404


# --- Protect the last active Owner -----------------------------------------


def test_cannot_deactivate_the_last_active_owner(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    for db in _db():
        from business_os.identity.models import User
        owner = db.scalar(select(User).where(User.email == OWNER_EMAIL))  # type: ignore[attr-defined]
        owner_id = str(owner.id)

    resp = client.patch(f"/api/v1/users/{owner_id}",
                        headers={"X-CSRF-Token": str(me["csrf_token"])},
                        json={"is_active": False})
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.employees.last_owner_protected"


def test_cannot_demote_the_last_active_owner(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    for db in _db():
        from business_os.identity.models import User
        owner = db.scalar(select(User).where(User.email == OWNER_EMAIL))  # type: ignore[attr-defined]
        owner_id = str(owner.id)

    resp = client.patch(f"/api/v1/users/{owner_id}",
                        headers={"X-CSRF-Token": str(me["csrf_token"])},
                        json={"is_owner": False})
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.employees.last_owner_protected"


def test_can_deactivate_an_owner_when_another_owner_remains(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}
    co_owner = client.post("/api/v1/users", headers=headers,
                           json=_employee_payload(is_owner=True)).json()

    for db in _db():
        from business_os.identity.models import User
        owner = db.scalar(select(User).where(User.email == OWNER_EMAIL))  # type: ignore[attr-defined]
        owner_id = str(owner.id)

    resp = client.patch(f"/api/v1/users/{owner_id}", headers=headers, json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    assert co_owner["is_owner"] is True  # the remaining owner is untouched


# --- Audit -------------------------------------------------------------


def test_create_and_update_are_recorded_in_tenant_audit_log(client: TestClient) -> None:
    company_id = _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}
    created = client.post("/api/v1/users", headers=headers,
                          json=_employee_payload()).json()
    client.patch(f"/api/v1/users/{created['id']}", headers=headers, json={"is_active": False})

    actions = _audit_actions(company_id)
    assert "employee_created" in actions
    assert "employee_updated" in actions


def test_idempotent_update_is_still_audited(client: TestClient) -> None:
    """Setting is_active to a value it already has changes nothing, but the
    attempt is still recorded — same discipline as platform_admin's
    entitlement grant/revoke."""
    company_id = _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}
    created = client.post("/api/v1/users", headers=headers,
                          json=_employee_payload()).json()
    before = _audit_actions(company_id).count("employee_updated")

    resp = client.patch(f"/api/v1/users/{created['id']}", headers=headers,
                        json={"is_active": True})  # already active
    assert resp.status_code == 200

    assert _audit_actions(company_id).count("employee_updated") == before + 1


# --- Independence from subscription state ----------------------------------


def test_create_is_blocked_when_subscription_suspended(client: TestClient) -> None:
    company_id = _seed_owner()
    _set_subscription_state(company_id, "suspended")
    me = _login(client)

    resp = client.post("/api/v1/users", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json=_employee_payload())
    assert resp.status_code == 402
    assert resp.json()["detail"]["message_key"] == "errors.subscription.mutations_blocked"


def test_employee_list_read_is_unaffected_by_suspension(client: TestClient) -> None:
    company_id = _seed_owner()
    _set_subscription_state(company_id, "suspended")
    _login(client)

    assert client.get("/api/v1/users").status_code == 200
