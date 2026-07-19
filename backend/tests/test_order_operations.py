"""Diagnosis (in-place edit + approval persistence), part/labor lines, accessories —
the ServiceOrder aggregate members (docs/01 §4), embedded in GET /orders/{id}."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _login(client: TestClient, company: str = "Сервиз А",
           email: str = "a@a.bg") -> dict[str, str]:
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, company, "Owner", email, "парола-123")
    me = client.post("/api/v1/auth/login",
                     json={"email": email, "password": "парола-123"}).json()
    return {"X-CSRF-Token": str(me["csrf_token"])}


def _order(client: TestClient, h: dict[str, str]) -> str:
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": "0888111222"}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone", "field_values": {"brand": "Apple"},
    }).json()["id"]
    return str(client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Не се включва",
    }).json()["id"])


def test_order_detail_embeds_empty_aggregate_by_default(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["diagnosis"] is None
    assert detail["part_lines"] == []
    assert detail["labor_lines"] == []
    assert detail["accessories"] == []
    assert detail["estimated_total"] == 0.0


def test_diagnosis_put_is_create_or_replace_in_place(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)

    r = client.put(f"/api/v1/orders/{oid}/diagnosis", headers=h, json={
        "observed": "Счупен екран", "cause": "Падане", "recommendation": "Смяна на дисплей",
        "estimated_cost": "120.00", "estimated_days": 2, "repairable": True,
        "approval_required": True,
    })
    assert r.status_code == 200
    assert r.json()["recommendation"] == "Смяна на дисплей"
    assert r.json()["estimated_cost"] == 120.0

    # Second PUT replaces in place — no versioning, same record.
    r2 = client.put(f"/api/v1/orders/{oid}/diagnosis", headers=h, json={
        "observed": "Счупен екран и батерия", "cause": "Падане",
        "recommendation": "Смяна на дисплей и батерия", "estimated_cost": "180.00",
        "estimated_days": 3, "repairable": True, "approval_required": True,
    })
    assert r2.status_code == 200
    assert r2.json()["recommendation"] == "Смяна на дисплей и батерия"

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["diagnosis"]["estimated_cost"] == 180.0

    events = [e["event_type"] for e in client.get(f"/api/v1/orders/{oid}/timeline").json()]
    assert events.count("diagnosis_recorded") == 1
    assert events.count("diagnosis_updated") == 1


def test_approval_persists_to_diagnosis_record(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    client.put(f"/api/v1/orders/{oid}/diagnosis", headers=h, json={
        "recommendation": "Смяна на дисплей", "estimated_cost": "120.00",
        "approval_required": True,
    })
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "waiting_customer"})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={
        "to": "repair", "approval": {"approved": True, "channel": "phone", "amount": 120},
    })

    detail = client.get(f"/api/v1/orders/{oid}").json()
    approval = detail["diagnosis"]["approval"]
    assert approval["approved"] is True
    assert approval["channel"] == "phone"
    assert "by_user" in approval and "at" in approval


def test_rejection_persists_to_diagnosis_record(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    client.put(f"/api/v1/orders/{oid}/diagnosis", headers=h,
              json={"recommendation": "x", "approval_required": True})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "waiting_customer"})
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "declined", "reason": "Клиентът отказа"})

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["diagnosis"]["approval"]["approved"] is False


def test_part_lines_lifecycle_and_state_validation(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)

    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "name": "Дисплей", "qty": 1, "unit_cost": "60.00", "unit_price": "100.00",
    })
    assert r.status_code == 201
    line_id = r.json()["id"]
    assert r.json()["state"] == "needed"

    r = client.patch(f"/api/v1/part-lines/{line_id}", headers=h, json={"state": "ordered"})
    assert r.status_code == 200
    assert r.json()["state"] == "ordered"

    r = client.patch(f"/api/v1/part-lines/{line_id}", headers=h,
                     json={"state": "not_a_state"})
    assert r.status_code == 400

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["part_lines"][0]["state"] == "ordered"
    assert detail["estimated_total"] == 100.0

    events = [e["event_type"] for e in client.get(f"/api/v1/orders/{oid}/timeline").json()]
    assert "part_added" in events
    assert "part_ordered" in events


def test_labor_lines_feed_estimated_total(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"name": "Дисплей", "qty": 1, "unit_cost": "60", "unit_price": "100"})
    client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
               json={"description": "Смяна на дисплей", "qty": 1, "unit_price": "50"})

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["estimated_total"] == 150.0
    assert detail["labor_lines"][0]["description"] == "Смяна на дисплей"


def test_accessories_returned_flag(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    item_id = client.post(f"/api/v1/orders/{oid}/accessories", headers=h,
                          json={"name": "Зарядно", "qty": 1}).json()["id"]
    assert client.get(f"/api/v1/orders/{oid}").json()["accessories"][0]["returned"] is False

    r = client.patch(f"/api/v1/accessories/{item_id}", headers=h, json={"returned": True})
    assert r.status_code == 200
    assert r.json()["returned"] is True


def test_aggregate_members_are_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid = _order(client, h_a)
    line_id = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h_a, json={
        "name": "Дисплей", "qty": 1, "unit_cost": "1", "unit_price": "1",
    }).json()["id"]
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    assert client.patch(f"/api/v1/part-lines/{line_id}", headers=h_b,
                        json={"state": "ordered"}).status_code == 404
