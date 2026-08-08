"""Company Legal Requisites (invoice-readiness prerequisite slice,
docs/ACCOUNTANT_REVIEW.md §4 R1/§2 T1): Owner-only read/update of
`companies.requisites`/`companies.vat_registered` through an explicit
allow-listed contract (`address`, `phone`, `vat_registered` only — the full
legal field set is an open accountant question, not implemented here).

No new table, no migration — `companies.requisites`/`vat_registered` already
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


def _seed_owner(company: str = "Сервиз А", email: str = OWNER_EMAIL) -> uuid.UUID:
    from business_os.identity.service import seed_company

    for db in _db():
        seeded = seed_company(db, company, "Мария", email, OWNER_PASSWORD, "1234")
        return seeded.id
    raise AssertionError("unreachable")


def _login(client: TestClient, email: str = OWNER_EMAIL,
          password: str = OWNER_PASSWORD) -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


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


def test_owner_can_read_requisites_defaulting_to_empty(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)

    resp = client.get("/api/v1/company/requisites",
                      headers={"X-CSRF-Token": str(me["csrf_token"])})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"address": None, "phone": None, "vat_registered": False}


def test_owner_can_update_requisites(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    resp = client.patch("/api/v1/company/requisites", headers=headers, json={
        "address": "гр. София, ул. Примерна 1", "phone": "029876543", "vat_registered": True,
    })
    assert resp.status_code == 200
    assert resp.json() == {
        "address": "гр. София, ул. Примерна 1", "phone": "029876543", "vat_registered": True,
    }

    # Persisted, not just echoed back.
    resp2 = client.get("/api/v1/company/requisites", headers=headers)
    assert resp2.json() == {
        "address": "гр. София, ул. Примерна 1", "phone": "029876543", "vat_registered": True,
    }


def test_partial_update_leaves_other_fields_untouched(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    client.patch("/api/v1/company/requisites", headers=headers,
                json={"address": "гр. Пловдив", "phone": "032111222"})
    resp = client.patch("/api/v1/company/requisites", headers=headers,
                        json={"phone": "032999888"})

    assert resp.status_code == 200
    assert resp.json()["address"] == "гр. Пловдив"
    assert resp.json()["phone"] == "032999888"


def test_vat_registered_can_be_toggled_off_again(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    client.patch("/api/v1/company/requisites", headers=headers, json={"vat_registered": True})
    resp = client.patch("/api/v1/company/requisites", headers=headers,
                        json={"vat_registered": False})

    assert resp.status_code == 200
    assert resp.json()["vat_registered"] is False


def test_unlisted_key_is_rejected(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    # "eik" is exactly the kind of field ACCOUNTANT_REVIEW.md R1 has not
    # approved yet — the contract must reject it outright, not silently drop
    # it or store it as an arbitrary extra key. FastAPI validation errors go
    # through the app's own docs/09 §1 envelope (main.py's
    # RequestValidationError handler), not a raw 422 body.
    resp = client.patch("/api/v1/company/requisites", headers=headers,
                        json={"eik": "123456789"})
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_worker_cannot_read_requisites(client: TestClient) -> None:
    _seed_owner()
    owner_me = _login(client)
    client.post("/api/v1/users", headers={"X-CSRF-Token": str(owner_me["csrf_token"])},
               json={"name": "Иво", "email": "ivo@a.bg", "password": "парола-за-иво-123"})
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": str(owner_me["csrf_token"])})

    worker_me = _login(client, email="ivo@a.bg", password="парола-за-иво-123")
    resp = client.get("/api/v1/company/requisites",
                      headers={"X-CSRF-Token": str(worker_me["csrf_token"])})
    assert resp.status_code == 403
    assert resp.json()["detail"]["message_key"] == "errors.auth.owner_required"


def test_worker_cannot_update_requisites(client: TestClient) -> None:
    _seed_owner()
    owner_me = _login(client)
    client.post("/api/v1/users", headers={"X-CSRF-Token": str(owner_me["csrf_token"])},
               json={"name": "Иво", "email": "ivo@a.bg", "password": "парола-за-иво-123"})
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": str(owner_me["csrf_token"])})

    worker_me = _login(client, email="ivo@a.bg", password="парола-за-иво-123")
    resp = client.patch("/api/v1/company/requisites",
                        headers={"X-CSRF-Token": str(worker_me["csrf_token"])},
                        json={"address": "опит за промяна"})
    assert resp.status_code == 403


def test_update_requires_csrf(client: TestClient) -> None:
    _seed_owner()
    _login(client)
    resp = client.patch("/api/v1/company/requisites", json={"address": "без CSRF"})
    assert resp.status_code == 403


def test_requisites_are_tenant_isolated(client: TestClient) -> None:
    _seed_owner("Сервиз А", OWNER_EMAIL)
    _seed_owner("Сервиз Б", "petar@b.bg")

    owner_a = _login(client, email=OWNER_EMAIL)
    client.patch("/api/v1/company/requisites",
                headers={"X-CSRF-Token": str(owner_a["csrf_token"])},
                json={"address": "Адрес на Фирма А", "vat_registered": True})
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": str(owner_a["csrf_token"])})

    owner_b = _login(client, email="petar@b.bg")
    resp = client.get("/api/v1/company/requisites",
                      headers={"X-CSRF-Token": str(owner_b["csrf_token"])})
    # Company B never wrote anything - must never see Company A's values,
    # confirming isolation without any client-suppliable company id to guess.
    assert resp.json() == {"address": None, "phone": None, "vat_registered": False}


def test_update_recorded_in_tenant_audit_log(client: TestClient) -> None:
    company_id = _seed_owner()
    me = _login(client)
    client.patch("/api/v1/company/requisites",
                headers={"X-CSRF-Token": str(me["csrf_token"])},
                json={"address": "гр. Варна"})

    assert "company_requisites_updated" in _audit_actions(company_id)


def test_update_blocked_when_subscription_suspended(client: TestClient) -> None:
    company_id = _seed_owner()
    _set_subscription_state(company_id, "suspended")
    me = _login(client)

    resp = client.patch("/api/v1/company/requisites",
                        headers={"X-CSRF-Token": str(me["csrf_token"])},
                        json={"address": "не трябва да мине"})
    assert resp.status_code == 402
    assert resp.json()["detail"]["message_key"] == "errors.subscription.mutations_blocked"


def test_requisites_read_is_unaffected_by_suspension(client: TestClient) -> None:
    company_id = _seed_owner()
    _set_subscription_state(company_id, "suspended")
    me = _login(client)

    resp = client.get("/api/v1/company/requisites",
                      headers={"X-CSRF-Token": str(me["csrf_token"])})
    assert resp.status_code == 200
