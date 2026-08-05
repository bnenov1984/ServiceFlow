"""Tenant self-service PIN setup (docs/business-os PIN self-service task):
POST /auth/pin lets the current user set or replace their own PIN — the gap
left by vendor provisioning never collecting one and `create_employee`'s
optional `pin` only covering an Owner setting one for someone *else*.
"""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _seed(company: str = "Сервиз А", email: str = "maria@a.bg",
          password: str = "парола-123", pin: str | None = None) -> None:
    """`pin=None` by default — mirrors a vendor-provisioned owner
    (`ProvisionCompanyRequest` has no PIN field at all), not the
    dev-seed convenience `test_auth.py`'s own `_seed` defaults to."""
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, company, "Мария", email, password, pin)


def _login(client: TestClient, email: str = "maria@a.bg",
           password: str = "парола-123") -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def test_newly_provisioned_owner_has_no_pin(client: TestClient) -> None:
    _seed()
    me = _login(client)
    assert me["has_pin"] is False

    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["has_pin"] is False

    resp = client.get("/api/v1/users")
    assert resp.status_code == 200
    assert [u["has_pin"] for u in resp.json()] == [False]


def test_self_service_pin_setup_works(client: TestClient) -> None:
    _seed()
    me = _login(client)
    csrf = str(me["csrf_token"])

    resp = client.post("/api/v1/auth/pin", headers={"X-CSRF-Token": csrf},
                       json={"pin": "4321"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["has_pin"] is True

    # The pin verifies through the exact same check pin-switch always uses -
    # same hashing, same code path, no parallel PIN mechanism.
    resp = client.post("/api/v1/auth/pin-switch", headers={"X-CSRF-Token": csrf},
                       json={"user_id": me["user_id"], "pin": "4321"})
    assert resp.status_code == 200, resp.text


def test_pin_can_be_changed(client: TestClient) -> None:
    _seed()
    me = _login(client)
    csrf = str(me["csrf_token"])

    client.post("/api/v1/auth/pin", headers={"X-CSRF-Token": csrf}, json={"pin": "1111"})
    resp = client.post("/api/v1/auth/pin", headers={"X-CSRF-Token": csrf}, json={"pin": "2222"})
    assert resp.status_code == 200

    old_pin = client.post("/api/v1/auth/pin-switch", headers={"X-CSRF-Token": csrf},
                          json={"user_id": me["user_id"], "pin": "1111"})
    assert old_pin.status_code == 401

    new_pin = client.post("/api/v1/auth/pin-switch", headers={"X-CSRF-Token": csrf},
                          json={"user_id": me["user_id"], "pin": "2222"})
    assert new_pin.status_code == 200


def test_another_user_cannot_set_someone_elses_pin_through_this_endpoint(
    client: TestClient,
) -> None:
    """The request schema has no `user_id` field at all - this proves it in
    practice, not just by reading the schema: worker A's call can only ever
    touch worker A's own row, even when a stray `user_id` field is smuggled
    into the body (Pydantic drops unknown fields; FastAPI never sees it)."""
    import os as _os

    from business_os.identity import security
    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    _seed()
    owner_me = _login(client)

    for db in open_session(_os.environ["SERVICEFLOW_DATABASE_URL"]):
        from sqlalchemy import select

        owner = db.scalar(select(User).where(User.email == "maria@a.bg"))
        assert owner is not None
        worker = User(company_id=owner.company_id, name="Иво", email="ivo@a.bg",
                      password_hash=security.hash_secret("парола-456"))
        db.add(worker)
        db.commit()
        worker_id = str(worker.id)

    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": str(owner_me["csrf_token"])})
    worker_me = _login(client, email="ivo@a.bg", password="парола-456")
    worker_csrf = str(worker_me["csrf_token"])

    resp = client.post(
        "/api/v1/auth/pin", headers={"X-CSRF-Token": worker_csrf},
        json={"pin": "9999", "user_id": str(owner_me["user_id"])},
    )
    assert resp.status_code == 200

    for db in open_session(_os.environ["SERVICEFLOW_DATABASE_URL"]):
        from sqlalchemy import select as _select

        owner_row = db.scalar(_select(User).where(User.id == owner_me["user_id"]))  # type: ignore[arg-type]
        assert owner_row is not None
        assert owner_row.pin_hash is None  # untouched by the worker's call

        worker_row = db.scalar(_select(User).where(User.id == worker_id))  # type: ignore[arg-type]
        assert worker_row is not None
        assert worker_row.pin_hash is not None  # the worker's own row changed instead


def test_set_pin_requires_csrf(client: TestClient) -> None:
    _seed()
    _login(client)
    resp = client.post("/api/v1/auth/pin", json={"pin": "4321"})
    assert resp.status_code == 403


def test_set_pin_rejects_too_short_pin(client: TestClient) -> None:
    _seed()
    me = _login(client)
    resp = client.post("/api/v1/auth/pin", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json={"pin": "12"})
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_set_pin_still_works_when_subscription_suspended(client: TestClient) -> None:
    """`/auth/pin` is identity/session mechanics, exempt from the mutation
    gate the same way `logout`/`pin-switch` already are (docs/09 §1) — a
    suspended company's owner must still be able to set a PIN and get into
    the app to see why (ADR-009's "all data visible" even while suspended)."""
    from business_os.identity.models import Company
    from business_os.shared_kernel.db import open_session

    _seed()
    me = _login(client)
    csrf = str(me["csrf_token"])

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        company = db.get(Company, me["company_id"])  # type: ignore[arg-type]
        assert company is not None
        company.subscription_state = "suspended"
        db.commit()  # type: ignore[attr-defined]

    resp = client.post("/api/v1/auth/pin", headers={"X-CSRF-Token": csrf}, json={"pin": "4321"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["has_pin"] is True


def test_pin_switch_still_rejects_a_user_with_no_pin(client: TestClient) -> None:
    """Regression guard: setting your own PIN must not change how pin-switch
    treats *other* still-pin-less users."""
    import os as _os

    from business_os.identity import security
    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    _seed()
    me = _login(client)
    csrf = str(me["csrf_token"])

    for db in open_session(_os.environ["SERVICEFLOW_DATABASE_URL"]):
        from sqlalchemy import select

        owner = db.scalar(select(User).where(User.email == "maria@a.bg"))
        assert owner is not None
        worker = User(company_id=owner.company_id, name="Иво", email="ivo@a.bg",
                      password_hash=security.hash_secret("парола-456"))
        db.add(worker)
        db.commit()
        worker_id = str(worker.id)

    resp = client.post("/api/v1/auth/pin-switch", headers={"X-CSRF-Token": csrf},
                       json={"user_id": worker_id, "pin": "0000"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["message_key"] == "errors.auth.invalid_pin"
