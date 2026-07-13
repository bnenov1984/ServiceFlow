"""Service orders API: numbering, transitions, approval, BR-2 unlock, warranty
return, timeline attribution, tenant isolation."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _login(client: TestClient, company: str = "Сервиз А",
           email: str = "a@a.bg") -> dict[str, str]:
    from serviceflow.identity.service import seed_company
    from serviceflow.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, company, "Owner", email, "парола-123")
    me = client.post("/api/v1/auth/login",
                     json={"email": email, "password": "парола-123"}).json()
    return {"X-CSRF-Token": str(me["csrf_token"])}


def _customer_and_asset(client: TestClient, h: dict[str, str],
                        phone: str = "0888111222") -> tuple[str, str]:
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": phone}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone", "field_values": {"brand": "Apple", "model": "13"},
    }).json()["id"]
    return cid, aid


def _order(client: TestClient, h: dict[str, str], cid: str, aid: str,
          complaint: str = "Не се включва") -> dict[str, object]:
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": complaint,
    })
    assert r.status_code == 201, r.text
    return dict(r.json())


def test_create_order_numbering_and_default_status(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    o1 = _order(client, h, cid, aid)
    o2 = _order(client, h, cid, aid, "Счупен екран")
    assert o1["status_code"] == "received"
    assert o1["status_kind"] == "working"
    year = str(__import__("datetime").date.today().year)
    assert o1["number"] == f"{year}-00001"
    assert o2["number"] == f"{year}-00002"


def test_asset_must_belong_to_customer(client: TestClient) -> None:
    h = _login(client)
    cid1, _ = _customer_and_asset(client, h, "0888111222")
    _, aid2 = _customer_and_asset(client, h, "0888333444")
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid1, "asset_id": aid2, "complaint": "x",
    })
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "asset_mismatch"


def test_status_transitions_ok_warn_no(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    order = _order(client, h, cid, aid)
    oid = order["id"]

    # received -> ready is WARN (skip allowed, warning surfaces).
    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "ready"})
    assert r.status_code == 200
    assert r.json()["warning"] == "skip"
    assert r.json()["status_code"] == "ready"

    # ready -> diagnostics is NO per the matrix.
    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.orders.invalid_transition"


def test_waiting_customer_requires_recorded_approval(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "waiting_customer"})

    # No approval payload -> blocked (BR-7).
    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "repair"})
    assert r.status_code == 400
    assert r.json()["detail"]["message_key"] == "errors.orders.approval_required"

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={
        "to": "repair", "approval": {"approved": True, "channel": "phone", "amount": 50},
    })
    assert r.status_code == 200
    assert r.json()["status_code"] == "repair"


def test_declined_requires_reason_and_is_terminal(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "waiting_customer"})

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "declined"})
    assert r.status_code == 400
    assert r.json()["detail"]["message_key"] == "errors.orders.reason_required"

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h,
                    json={"to": "declined", "reason": "Клиентът отказа офертата"})
    assert r.status_code == 200
    assert r.json()["status_kind"] == "terminal_failure"

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "repair"})
    assert r.status_code == 409  # terminal source is always NO


def test_delivery_flow_with_warranty(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]
    for to in ("diagnostics", "repair", "testing"):
        client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": to})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "ready"})

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h,
                    json={"to": "delivered", "warranty_days": 90})
    assert r.status_code == 200
    body = r.json()
    assert body["status_code"] == "delivered"
    assert body["warranty_days"] == 90
    assert body["delivered_at"] is not None


def test_cancelled_is_owner_only(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]

    from serviceflow.identity import security
    from serviceflow.identity.models import User
    from serviceflow.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        from sqlalchemy import select
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        worker = User(company_id=owner.company_id, name="Иво", email="ivo@a.bg",
                      password_hash=security.hash_secret("парола-456"),
                      pin_hash=security.hash_secret("5678"))
        db.add(worker)
        db.commit()

    r = client.post("/api/v1/auth/login", json={"email": "ivo@a.bg", "password": "парола-456"})
    assert r.status_code == 200
    csrf = r.json()["csrf_token"]

    r = client.post(f"/api/v1/orders/{oid}/status", headers={"X-CSRF-Token": csrf},
                    json={"to": "cancelled", "reason": "дублирана поръчка"})
    assert r.status_code == 403


def test_br2_unlock_owner_only_and_reverts_to_prior_status(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "cancelled", "reason": "по грешка"})

    r = client.post(f"/api/v1/orders/{oid}/unlock", headers=h,
                    json={"reason": "грешка на оператора"})
    assert r.status_code == 200
    assert r.json()["status_code"] == "diagnostics"

    events = client.get(f"/api/v1/orders/{oid}/timeline").json()
    types = [e["event_type"] for e in events]
    assert "order_unlocked" in types


def test_br2_unlock_requires_reason(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "cancelled", "reason": "x"})
    r = client.post(f"/api/v1/orders/{oid}/unlock", headers=h, json={"reason": "  "})
    assert r.status_code == 400


def test_reopen_via_ui_button_is_a_new_linked_order_not_a_status_change(
    client: TestClient,
) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]
    for to in ("diagnostics", "repair", "testing", "ready"):
        client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": to})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "delivered"})

    r = client.post(f"/api/v1/orders/{oid}/warranty-return", headers=h,
                    json={"complaint": "Отново не се включва"})
    assert r.status_code == 201
    new_order = r.json()
    assert new_order["id"] != oid
    assert new_order["origin_order_id"] == oid
    assert new_order["status_code"] == "received"

    # The original stays terminal and untouched.
    original = client.get(f"/api/v1/orders/{oid}").json()
    assert original["status_code"] == "delivered"


def test_warranty_return_requires_delivered_source(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]
    r = client.post(f"/api/v1/orders/{oid}/warranty-return", headers=h,
                    json={"complaint": "x"})
    assert r.status_code == 409


def test_timeline_records_actor_and_survives_pin_switch(client: TestClient) -> None:
    from serviceflow.identity import security
    from serviceflow.identity.models import User
    from serviceflow.shared_kernel.db import open_session

    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        from sqlalchemy import select
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        worker = User(company_id=owner.company_id, name="Иво", email="ivo2@a.bg",
                      password_hash=security.hash_secret("x"),
                      pin_hash=security.hash_secret("5678"))
        db.add(worker)
        db.commit()
        worker_id = str(worker.id)

    r = client.post("/api/v1/auth/pin-switch", headers=h,
                    json={"user_id": worker_id, "pin": "5678"})
    assert r.status_code == 200

    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    events = client.get(f"/api/v1/orders/{oid}/timeline").json()
    status_event = next(e for e in events if e["event_type"] == "status_changed")
    assert status_event["actor_user_id"] == worker_id


def test_orders_are_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    cid, aid = _customer_and_asset(client, h_a)
    oid = _order(client, h_a, cid, aid)["id"]
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    assert client.get(f"/api/v1/orders/{oid}").status_code == 404
    assert client.get(f"/api/v1/orders/{oid}/timeline").status_code == 404
    assert client.get("/api/v1/orders").json() == []
