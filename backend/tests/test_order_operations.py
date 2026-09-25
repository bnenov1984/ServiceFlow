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
    # Wave 2 Issue 33: "ordered" is the default active state for a newly
    # created part line (assigned/requested regardless of physical stock).
    assert r.json()["state"] == "ordered"

    r = client.patch(f"/api/v1/part-lines/{line_id}", headers=h, json={"state": "installed"})
    assert r.status_code == 200
    assert r.json()["state"] == "installed"

    r = client.patch(f"/api/v1/part-lines/{line_id}", headers=h,
                     json={"state": "not_a_state"})
    assert r.status_code == 400

    # The old 5-state model's values are no longer accepted either — the
    # simplified V1 model has exactly two active states.
    r = client.patch(f"/api/v1/part-lines/{line_id}", headers=h, json={"state": "needed"})
    assert r.status_code == 400

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["part_lines"][0]["state"] == "installed"
    assert detail["estimated_total"] == 100.0

    events = [e["event_type"] for e in client.get(f"/api/v1/orders/{oid}/timeline").json()]
    assert "part_added" in events
    assert "part_state_changed" in events


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


# --- Wave 4 PART WARRANTY (issue 05, 2026-09-25: unit changed to months) --

def test_part_line_warranty_months_persistence_and_validation(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)

    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "name": "Дисплей", "unit_price": "100.00", "warranty_months": 3,
    })
    assert r.status_code == 201, r.text
    assert r.json()["warranty_months"] == 3
    line_id = r.json()["id"]

    # Explicit 0 — "Без гаранция", distinct from never having been set.
    r2 = client.patch(f"/api/v1/part-lines/{line_id}", headers=h, json={"warranty_months": 0})
    assert r2.status_code == 200
    assert r2.json()["warranty_months"] == 0

    r3 = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "name": "Батерия", "unit_price": "1", "warranty_months": -1,
    })
    assert r3.status_code == 400
    assert r3.json()["message_key"] == "errors.validation"


def test_part_line_warranty_months_defaults_to_none(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                    json={"name": "Дисплей", "unit_price": "100.00"})
    assert r.json()["warranty_months"] is None


def test_part_line_warranty_months_round_trips_whole_months(client: TestClient) -> None:
    """The PO's own examples (12, 6 месеца) — 30-days/month must round-trip
    these exactly, not just approximately."""
    h = _login(client)
    oid = _order(client, h)

    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "name": "Дисплей", "unit_price": "100.00", "warranty_months": 12,
    })
    assert r.json()["warranty_months"] == 12

    r2 = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "name": "Батерия", "unit_price": "50.00", "warranty_months": 6,
    })
    assert r2.json()["warranty_months"] == 6


# --- Wave 4 TERMINAL ORDER IMMUTABILITY ----------------------------------

def _cancel(client: TestClient, h: dict[str, str], oid: str) -> None:
    r = client.post(f"/api/v1/orders/{oid}/status", headers=h,
                    json={"to": "cancelled", "reason": "Клиентът се отказа"})
    assert r.status_code == 200, r.text


def test_terminal_order_rejects_diagnosis_mutation(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    _cancel(client, h, oid)

    r = client.put(f"/api/v1/orders/{oid}/diagnosis", headers=h,
                   json={"recommendation": "опит след приключване"})
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.orders.terminal_readonly"


def test_terminal_order_rejects_part_line_add_and_patch(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    line_id = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "name": "Дисплей", "unit_price": "100.00",
    }).json()["id"]
    _cancel(client, h, oid)

    r_add = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                        json={"name": "Батерия", "unit_price": "1"})
    assert r_add.status_code == 409
    assert r_add.json()["detail"]["message_key"] == "errors.orders.terminal_readonly"

    r_patch = client.patch(f"/api/v1/part-lines/{line_id}", headers=h,
                           json={"state": "installed"})
    assert r_patch.status_code == 409
    assert r_patch.json()["detail"]["message_key"] == "errors.orders.terminal_readonly"


def test_terminal_order_rejects_labor_line_add_and_patch(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    line_id = client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h, json={
        "description": "Диагностика", "unit_price": "20",
    }).json()["id"]
    _cancel(client, h, oid)

    r_add = client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
                        json={"description": "Ремонт", "unit_price": "50"})
    assert r_add.status_code == 409
    assert r_add.json()["detail"]["message_key"] == "errors.orders.terminal_readonly"

    r_patch = client.patch(f"/api/v1/labor-lines/{line_id}", headers=h,
                           json={"unit_price": "99"})
    assert r_patch.status_code == 409
    assert r_patch.json()["detail"]["message_key"] == "errors.orders.terminal_readonly"


def test_terminal_order_rejects_accessory_add_and_patch(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    item_id = client.post(f"/api/v1/orders/{oid}/accessories", headers=h,
                          json={"name": "Зарядно", "qty": 1}).json()["id"]
    _cancel(client, h, oid)

    r_add = client.post(f"/api/v1/orders/{oid}/accessories", headers=h,
                        json={"name": "Кутия", "qty": 1})
    assert r_add.status_code == 409
    assert r_add.json()["detail"]["message_key"] == "errors.orders.terminal_readonly"

    r_patch = client.patch(f"/api/v1/accessories/{item_id}", headers=h, json={"returned": True})
    assert r_patch.status_code == 409
    assert r_patch.json()["detail"]["message_key"] == "errors.orders.terminal_readonly"


def test_terminal_order_read_endpoints_remain_unaffected(client: TestClient) -> None:
    """Only mutation is blocked — GET must keep working exactly as before,
    otherwise the order page itself couldn't render a terminal order."""
    h = _login(client)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"name": "Дисплей", "unit_price": "100.00"})
    _cancel(client, h, oid)

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["part_lines"][0]["name"] == "Дисплей"
    assert client.get(f"/api/v1/orders/{oid}/part-lines").status_code == 200


def test_documented_terminal_exceptions_are_unaffected_by_the_new_guard(
    client: TestClient,
) -> None:
    """docs/01: terminal orders accept payments settling an outstanding
    balance, and archiving — those two are deliberately NOT routed through
    _reject_if_terminal and must keep working exactly as before."""
    h = _login(client)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"name": "Дисплей", "unit_price": "100.00"})
    _cancel(client, h, oid)

    payment = client.post(f"/api/v1/orders/{oid}/payments", headers=h,
                          json={"amount": "50.00", "method": "cash", "note": ""})
    assert payment.status_code == 201, payment.text

    archived = client.post(f"/api/v1/orders/{oid}/archive", headers=h)
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived"] is True
