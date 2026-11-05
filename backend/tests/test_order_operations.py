"""Diagnosis (in-place edit + approval persistence), part/labor lines
(order-workflow-revamp WP-I: catalog-only creation, status-gated, BR-3
snapshot), order adjustments, accessories — the ServiceOrder aggregate
members (docs/01 §4), embedded in GET /orders/{id}."""

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
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]
    return str(client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Не се включва",
    }).json()["id"])


def _technician_id(client: TestClient, h: dict[str, str]) -> str:
    """order-workflow-revamp WP-G (Q2a): diagnostics now requires a
    technician on file — the Owner is itself a valid one (Q22)."""
    return str(next(u["id"] for u in client.get("/api/v1/users", headers=h).json()
                    if u["is_owner"]))


def _order_for_lines(client: TestClient, h: dict[str, str]) -> str:
    """order-workflow-revamp WP-I (Q13d): a line can only be added once the
    order has left „Приета" — every test below that adds a part/labor line
    needs this instead of the bare `_order()`."""
    oid = _order(client, h)
    r = client.post(f"/api/v1/orders/{oid}/status", headers=h,
                    json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    assert r.status_code == 200, r.text
    return oid


def _catalog_item(client: TestClient, h: dict[str, str], *, kind: str = "part",
                  name: str = "Дисплей", unit: str = "pcs", sale_price: str = "100.00",
                  unit_cost: str | None = None, code: str | None = None) -> str:
    body: dict[str, object] = {"kind": kind, "name": name, "unit": unit,
                               "sale_price": sale_price}
    if unit_cost is not None:
        body["unit_cost"] = unit_cost
    if code is not None:
        body["code"] = code
    r = client.post("/api/v1/catalog-items", headers=h, json=body)
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def test_order_detail_embeds_empty_aggregate_by_default(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["diagnosis"] is None
    assert detail["part_lines"] == []
    assert detail["labor_lines"] == []
    assert detail["accessories"] == []
    assert detail["adjustments"] == []
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
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
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
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "waiting_customer"})
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "declined", "reason": "Клиентът отказа"})

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["diagnosis"]["approval"]["approved"] is False


def test_part_lines_lifecycle_and_state_validation(client: TestClient) -> None:
    h = _login(client)
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, name="Дисплей", sale_price="100.00")

    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "catalog_item_id": item_id, "qty": 1,
    })
    assert r.status_code == 201, r.text
    line_id = r.json()["id"]
    assert r.json()["name"] == "Дисплей"
    assert r.json()["catalog_item_id"] == item_id
    # order-workflow-revamp WP-J (Q15b): "issued" (от наличност) is the
    # default when a caller doesn't say otherwise.
    assert r.json()["state"] == "issued"

    r = client.patch(f"/api/v1/part-lines/{line_id}", headers=h, json={"state": "installed"})
    assert r.status_code == 200
    assert r.json()["state"] == "installed"

    r = client.patch(f"/api/v1/part-lines/{line_id}", headers=h,
                     json={"state": "not_a_state"})
    assert r.status_code == 400

    # The pre-WP-J 5-state model's retired values are no longer accepted
    # either — the current model has exactly three active states.
    r = client.patch(f"/api/v1/part-lines/{line_id}", headers=h, json={"state": "needed"})
    assert r.status_code == 400

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["part_lines"][0]["state"] == "installed"
    assert detail["estimated_total"] == 100.0

    events = [e["event_type"] for e in client.get(f"/api/v1/orders/{oid}/timeline").json()]
    assert "part_added" in events
    assert "part_state_changed" in events


def test_part_line_add_rejects_installed_as_an_initial_state(client: TestClient) -> None:
    """order-workflow-revamp WP-J (Q15b): the add form offers exactly two
    buttons (от наличност/поръчай) — "installed" is only ever reached via a
    later PATCH, never as the line's starting state."""
    h = _login(client)
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, name="Дисплей", sale_price="100.00")

    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "catalog_item_id": item_id, "state": "installed",
    })
    assert r.status_code == 400
    assert r.json()["detail"]["message_key"] == "errors.part_lines.invalid_state"


def test_part_line_ordered_from_diagnostics_suggests_waiting_parts(client: TestClient) -> None:
    """Q5: marking a part поръчана from a working status that allows a
    Чака части move is a one-click *nudge*, not an automatic transition —
    the order's own status is untouched by the add itself."""
    h = _login(client)
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, name="Дисплей", sale_price="100.00")

    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "catalog_item_id": item_id, "state": "ordered",
    })
    assert r.status_code == 201, r.text
    assert r.json()["suggested_status"] == "waiting_parts"
    assert client.get(f"/api/v1/orders/{oid}").json()["status_code"] == "diagnostics"


def test_part_line_issued_from_stock_suggests_nothing(client: TestClient) -> None:
    h = _login(client)
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, name="Дисплей", sale_price="100.00")

    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "catalog_item_id": item_id, "state": "issued",
    })
    assert r.status_code == 201, r.text
    assert r.json()["suggested_status"] is None


def test_part_line_arriving_suggests_repair_only_when_last_ordered_line_clears(
    client: TestClient,
) -> None:
    """Q5c: the suggestion only fires once *no* line is still поръчана, and
    only while the order is actually paused in Чака части."""
    h = _login(client)
    oid = _order_for_lines(client, h)
    display_id = _catalog_item(client, h, name="Дисплей", sale_price="100.00")
    battery_id = _catalog_item(client, h, name="Батерия", sale_price="20.00")

    display_line = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "catalog_item_id": display_id, "state": "ordered",
    }).json()
    battery_line = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "catalog_item_id": battery_id, "state": "ordered",
    }).json()
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "waiting_parts"})

    r1 = client.patch(f"/api/v1/part-lines/{display_line['id']}", headers=h,
                      json={"state": "issued"})
    assert r1.status_code == 200
    assert r1.json()["suggested_status"] is None  # the battery is still поръчана

    r2 = client.patch(f"/api/v1/part-lines/{battery_line['id']}", headers=h,
                      json={"state": "issued"})
    assert r2.status_code == 200
    assert r2.json()["suggested_status"] == "repair"


def test_part_line_has_warranty_defaults_to_true_and_can_be_toggled(client: TestClient) -> None:
    """order-workflow-revamp WP-J (Q14/Q14b/Q14c): a plain on/off flag,
    defaulting on, that never affects the line's price."""
    h = _login(client)
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, name="Дисплей", sale_price="100.00")

    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                    json={"catalog_item_id": item_id})
    assert r.json()["has_warranty"] is True
    line_id = r.json()["id"]

    battery_id = _catalog_item(client, h, name="Батерия", sale_price="20.00")
    r2 = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "catalog_item_id": battery_id, "has_warranty": False,
    })
    assert r2.status_code == 201, r2.text
    assert r2.json()["has_warranty"] is False
    assert r2.json()["unit_price"] == 20.0  # Q14b: the flag never changes price

    r3 = client.patch(f"/api/v1/part-lines/{line_id}", headers=h, json={"has_warranty": False})
    assert r3.status_code == 200
    assert r3.json()["has_warranty"] is False
    assert r3.json()["unit_price"] == 100.0


def test_labor_lines_feed_estimated_total(client: TestClient) -> None:
    h = _login(client)
    oid = _order_for_lines(client, h)
    part_id = _catalog_item(client, h, kind="part", name="Дисплей", sale_price="100")
    labor_id = _catalog_item(client, h, kind="labor", name="Смяна на дисплей", sale_price="50")
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"catalog_item_id": part_id, "qty": 1})
    client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
               json={"catalog_item_id": labor_id, "qty": "1"})

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["estimated_total"] == 150.0
    assert detail["labor_lines"][0]["description"] == "Смяна на дисплей"


def test_labor_line_hourly_fractional_qty(client: TestClient) -> None:
    """ADR-BOS-013 §8: an hourly catalog item (unit="hour") accepts a
    fractional qty — 1.5 ч. × 40 lv/ч. = 60 lv."""
    h = _login(client)
    oid = _order_for_lines(client, h)
    labor_id = _catalog_item(client, h, kind="labor", name="Труд (час)",
                             unit="hour", sale_price="40.00")

    r = client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
                    json={"catalog_item_id": labor_id, "qty": "1.5"})
    assert r.status_code == 201, r.text
    assert r.json()["qty"] == 1.5
    assert r.json()["unit"] == "hour"

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["estimated_total"] == 60.0


def test_part_line_catalog_item_snapshotted_not_live(client: TestClient) -> None:
    """BR-3: a later catalog price change must never retroactively change an
    already-added line (ADR-BOS-013 §4)."""
    h = _login(client)
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, name="Дисплей", sale_price="100.00")

    line = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                       json={"catalog_item_id": item_id, "qty": 1}).json()
    assert line["unit_price"] == 100.0

    patched = client.patch(f"/api/v1/catalog-items/{item_id}", headers=h,
                           json={"sale_price": "150.00"})
    assert patched.status_code == 200, patched.text

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["part_lines"][0]["unit_price"] == 100.0


def test_part_line_rejects_unknown_catalog_item(client: TestClient) -> None:
    h = _login(client)
    oid = _order_for_lines(client, h)
    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                    json={"catalog_item_id": "01968f3e-0000-7000-8000-000000000000", "qty": 1})
    assert r.status_code == 404
    assert r.json()["detail"]["message_key"] == "errors.catalog.not_found"


def test_part_line_rejects_wrong_kind_catalog_item(client: TestClient) -> None:
    h = _login(client)
    oid = _order_for_lines(client, h)
    labor_id = _catalog_item(client, h, kind="labor", name="Труд")
    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                    json={"catalog_item_id": labor_id, "qty": 1})
    assert r.status_code == 400
    assert r.json()["detail"]["message_key"] == "errors.catalog.wrong_kind"


def test_part_line_rejects_archived_catalog_item(client: TestClient) -> None:
    h = _login(client)
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, name="Дисплей")
    client.post(f"/api/v1/catalog-items/{item_id}/archive", headers=h)

    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                    json={"catalog_item_id": item_id, "qty": 1})
    assert r.status_code == 400
    assert r.json()["detail"]["message_key"] == "errors.catalog.archived"


def test_line_creation_blocked_outside_allowed_statuses(client: TestClient) -> None:
    """order-workflow-revamp WP-I (Q13d): лини само в Диагностика/Чака
    клиент/Чака части/Ремонт — never at intake ("received"), never "ready"."""
    h = _login(client)
    oid = _order(client, h)  # stays "received" — no transition
    item_id = _catalog_item(client, h, name="Дисплей")

    r = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                    json={"catalog_item_id": item_id, "qty": 1})
    assert r.status_code == 400
    assert r.json()["detail"]["message_key"] == "errors.orders.lines_not_allowed_in_status"

    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "ready"})
    r2 = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                     json={"catalog_item_id": item_id, "qty": 1})
    assert r2.status_code == 400
    assert r2.json()["detail"]["message_key"] == "errors.orders.lines_not_allowed_in_status"


def test_accessories_returned_flag(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    item_id = client.post(f"/api/v1/orders/{oid}/accessories", headers=h,
                          json={"name": "Зарядно", "qty": 1}).json()["id"]
    assert client.get(f"/api/v1/orders/{oid}").json()["accessories"][0]["returned"] is False

    r = client.patch(f"/api/v1/accessories/{item_id}", headers=h, json={"returned": True})
    assert r.status_code == 200
    assert r.json()["returned"] is True


def _automotive_vehicle_order(client: TestClient, h: dict[str, str],
                              email: str = "a@a.bg") -> str:
    """order-workflow-revamp WP-H (Q16/Q16b): a vehicle order on a company
    whose profile is automotive_repair — the one combination whose asset
    type has `accessories: false` (migration 0036)."""
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.identity.service import set_business_profile
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.assets.service import seed_default_types

    for db in open_session(os.environ["SERVICEFLOW_TEST_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == email))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        set_business_profile(db, owner.company_id, "automotive_repair")
        seed_default_types(db, owner.company_id, "automotive_repair")
        db.commit()

    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": "0888111222"}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle", "field_values": {"brand": "Volkswagen", "model": "Golf"},
    }).json()["id"]
    return str(client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Скърца",
    }).json()["id"])


def test_accessory_add_rejected_for_asset_type_with_accessories_disabled(
    client: TestClient,
) -> None:
    h = _login(client)
    oid = _automotive_vehicle_order(client, h)

    r = client.post(f"/api/v1/orders/{oid}/accessories", headers=h,
                    json={"name": "Зарядно", "qty": 1})
    assert r.status_code == 400
    assert r.json()["detail"]["message_key"] == "errors.accessories.not_supported"


def test_aggregate_members_are_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid = _order_for_lines(client, h_a)
    item_id = _catalog_item(client, h_a, name="Дисплей", sale_price="1")
    line_id = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h_a, json={
        "catalog_item_id": item_id, "qty": 1,
    }).json()["id"]
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    assert client.patch(f"/api/v1/part-lines/{line_id}", headers=h_b,
                        json={"state": "ordered"}).status_code == 404


# --- Order adjustments (WP-I, Q13, resolves docs/01 OQ-5) -------------------

def test_adjustment_feeds_estimated_total(client: TestClient) -> None:
    h = _login(client)
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, name="Дисплей", sale_price="100.00")
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"catalog_item_id": item_id, "qty": 1})

    r = client.post(f"/api/v1/orders/{oid}/adjustments", headers=h,
                    json={"amount": "-20.00", "reason": "Лоялен клиент"})
    assert r.status_code == 201, r.text
    assert r.json()["amount"] == -20.0
    assert r.json()["reason"] == "Лоялен клиент"

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["estimated_total"] == 80.0
    assert detail["adjustments"][0]["reason"] == "Лоялен клиент"

    events = [e["event_type"] for e in client.get(f"/api/v1/orders/{oid}/timeline").json()]
    assert "adjustment_added" in events


def test_adjustment_requires_owner(client: TestClient) -> None:
    from business_os.identity import security
    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    h = _login(client)
    oid = _order_for_lines(client, h)

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        from sqlalchemy import select
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        worker = User(company_id=owner.company_id, name="Иво", email="ivo@a.bg",
                      password_hash=security.hash_secret("парола-123"))
        db.add(worker)
        db.commit()

    h_worker = {"X-CSRF-Token": str(client.post(
        "/api/v1/auth/login", json={"email": "ivo@a.bg", "password": "парола-123"},
    ).json()["csrf_token"])}

    r = client.post(f"/api/v1/orders/{oid}/adjustments", headers=h_worker,
                    json={"amount": "-10.00", "reason": "x"})
    assert r.status_code == 403


def test_adjustment_requires_reason(client: TestClient) -> None:
    h = _login(client)
    oid = _order_for_lines(client, h)
    r = client.post(f"/api/v1/orders/{oid}/adjustments", headers=h,
                    json={"amount": "-10.00", "reason": ""})
    assert r.status_code == 400
    assert r.json()["message_key"] == "errors.validation"


def test_adjustment_rejected_on_terminal_order(client: TestClient) -> None:
    h = _login(client)
    oid = _order_for_lines(client, h)
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "cancelled", "reason": "дубликат"})

    r = client.post(f"/api/v1/orders/{oid}/adjustments", headers=h,
                    json={"amount": "-10.00", "reason": "x"})
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.orders.terminal_readonly"


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
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, name="Дисплей", sale_price="100.00")
    line_id = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h, json={
        "catalog_item_id": item_id,
    }).json()["id"]
    _cancel(client, h, oid)

    r_add = client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                        json={"catalog_item_id": item_id})
    assert r_add.status_code == 409
    assert r_add.json()["detail"]["message_key"] == "errors.orders.terminal_readonly"

    r_patch = client.patch(f"/api/v1/part-lines/{line_id}", headers=h,
                           json={"state": "installed"})
    assert r_patch.status_code == 409
    assert r_patch.json()["detail"]["message_key"] == "errors.orders.terminal_readonly"


def test_terminal_order_rejects_labor_line_add_and_patch(client: TestClient) -> None:
    h = _login(client)
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, kind="labor", name="Диагностика", sale_price="20")
    line_id = client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h, json={
        "catalog_item_id": item_id,
    }).json()["id"]
    _cancel(client, h, oid)

    r_add = client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
                        json={"catalog_item_id": item_id})
    assert r_add.status_code == 409
    assert r_add.json()["detail"]["message_key"] == "errors.orders.terminal_readonly"

    r_patch = client.patch(f"/api/v1/labor-lines/{line_id}", headers=h,
                           json={"duration_min": 30})
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
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, name="Дисплей", sale_price="100.00")
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"catalog_item_id": item_id})
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
    oid = _order_for_lines(client, h)
    item_id = _catalog_item(client, h, name="Дисплей", sale_price="100.00")
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"catalog_item_id": item_id})
    _cancel(client, h, oid)

    payment = client.post(f"/api/v1/orders/{oid}/payments", headers=h,
                          json={"amount": "50.00", "method": "cash", "note": ""})
    assert payment.status_code == 201, payment.text

    archived = client.post(f"/api/v1/orders/{oid}/archive", headers=h)
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived"] is True
