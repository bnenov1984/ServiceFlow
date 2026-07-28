"""Login, session, CSRF, PIN-switch behavior (docs/09 contracts, ADR-008)."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _seed(company: str = "Сервиз А", email: str = "maria@a.bg",
          password: str = "парола-123", pin: str | None = "1234") -> None:
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, company, "Мария", email, password, pin)


def _login(client: TestClient, email: str = "maria@a.bg",
           password: str = "парола-123") -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def test_login_me_logout(client: TestClient) -> None:
    _seed()
    me = _login(client)
    assert me["is_owner"] is True
    assert client.cookies.get("sf_session")

    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "maria@a.bg"

    # Mutations without CSRF header are rejected (docs/09 §1).
    assert client.post("/api/v1/auth/logout").status_code == 403

    csrf = str(me["csrf_token"])
    resp = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_wrong_password_and_message_key_contract(client: TestClient) -> None:
    _seed()
    resp = client.post("/api/v1/auth/login",
                       json={"email": "maria@a.bg", "password": "грешна"})
    assert resp.status_code == 401
    detail = resp.json()["detail"]
    assert detail["message_key"] == "errors.auth.invalid_credentials"


def test_login_rate_limit(client: TestClient) -> None:
    from business_os.identity import service

    service._failures.clear()
    _seed()
    for _ in range(5):
        client.post("/api/v1/auth/login",
                    json={"email": "maria@a.bg", "password": "грешна"})
    resp = client.post("/api/v1/auth/login",
                       json={"email": "maria@a.bg", "password": "парола-123"})
    assert resp.status_code == 429
    service._failures.clear()


def test_pin_switch_changes_acting_user(client: TestClient) -> None:
    import os as _os

    from business_os.identity import security
    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    _seed()
    me = _login(client)
    csrf = str(me["csrf_token"])

    # Second worker in the same company, created directly here rather than via
    # POST /users (tests/test_employee_management.py covers that API) — this
    # test is only about PIN-switch, not employee creation.
    for db in open_session(_os.environ["SERVICEFLOW_DATABASE_URL"]):
        from sqlalchemy import select

        owner = db.scalar(select(User).where(User.email == "maria@a.bg"))
        assert owner is not None
        worker = User(company_id=owner.company_id, name="Иво", email="ivo@a.bg",
                      password_hash=security.hash_secret("парола-456"),
                      pin_hash=security.hash_secret("5678"))
        db.add(worker)
        db.commit()
        worker_id = str(worker.id)

    resp = client.post("/api/v1/auth/pin-switch", headers={"X-CSRF-Token": csrf},
                       json={"user_id": worker_id, "pin": "0000"})
    assert resp.status_code == 401  # wrong PIN

    resp = client.post("/api/v1/auth/pin-switch", headers={"X-CSRF-Token": csrf},
                       json={"user_id": worker_id, "pin": "5678"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Иво"
    assert resp.json()["is_owner"] is False
