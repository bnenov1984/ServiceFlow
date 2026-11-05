"""Service orders API: numbering, transitions, approval, BR-2 unlock, warranty
return, timeline attribution, tenant isolation."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _login(client: TestClient, company: str = "Сервиз А", email: str = "a@a.bg",
           business_profile: str = "generic_repair") -> dict[str, str]:
    """order-workflow-revamp WP-C (Q18): generic_repair (the default here)
    only seeds "other" now, not "vehicle" — _vehicle_customer_and_asset
    needs an explicit automotive_repair login."""
    from sqlalchemy import select

    from business_os.identity.service import seed_company, set_business_profile
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.assets.models import AssetType
    from serviceflow.assets.service import BUSINESS_PROFILE_ASSET_TYPES, seed_default_types

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        c = seed_company(db, company, "Owner", email, "парола-123")
        if business_profile != "generic_repair":
            set_business_profile(db, c.id, business_profile)
            bind_tenant_scope(db, c.id)
            target_code = BUSINESS_PROFILE_ASSET_TYPES[business_profile]["code"]
            already = db.scalar(select(AssetType).where(
                AssetType.company_id == c.id, AssetType.code == target_code,
            ))
            if already is None:
                seed_default_types(db, c.id, business_profile)
            db.commit()
    me = client.post("/api/v1/auth/login",
                     json={"email": email, "password": "парола-123"}).json()
    return {"X-CSRF-Token": str(me["csrf_token"])}


def _customer_and_asset(client: TestClient, h: dict[str, str],
                        phone: str = "0888111222") -> tuple[str, str]:
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": phone}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple 13"},
    }).json()["id"]
    return cid, aid


def _order(client: TestClient, h: dict[str, str], cid: str, aid: str,
          complaint: str = "Не се включва") -> dict[str, object]:
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": complaint,
    })
    assert r.status_code == 201, r.text
    return dict(r.json())


def _technician_id(client: TestClient, h: dict[str, str]) -> str:
    """order-workflow-revamp WP-G (Q2a): entering "diagnostics" (or any later
    WORKING status) now requires a technician already on file — the Owner
    created by `_login` is itself a valid technician (Q22), so every test
    below that doesn't care *which* technician just uses this one."""
    return str(next(u["id"] for u in client.get("/api/v1/users", headers=h).json()
                    if u["is_owner"]))


def test_create_order_numbering_and_default_status(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    o1 = _order(client, h, cid, aid)
    # WP-D (Q6): an asset can have at most one open order — close the first
    # before creating the second, which is all this test actually needs
    # (sequential numbering), not two orders open at once.
    client.post(f"/api/v1/orders/{o1['id']}/status", headers=h,
               json={"to": "declined", "reason": "Тест"})
    o2 = _order(client, h, cid, aid, "Счупен екран")
    assert o1["status_code"] == "received"
    assert o1["status_kind"] == "working"
    year = str(__import__("datetime").date.today().year)
    assert o1["number"] == f"{year}-00001"
    assert o2["number"] == f"{year}-00002"


def test_order_may_use_an_asset_owned_by_a_different_customer(client: TestClient) -> None:
    """Wave 3 Issue 20: the person bringing an asset in is not necessarily its
    current owner ("Използвай автомобила" keeps the vehicle under its
    existing owner while the order belongs to whoever is at the counter) —
    an order's customer_id and its asset's Asset.customer_id are deliberately
    independent, so this is now a valid order, not a 400."""
    h = _login(client)
    cid1, _ = _customer_and_asset(client, h, "0888111222")
    _, aid2 = _customer_and_asset(client, h, "0888333444")
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid1, "asset_id": aid2, "complaint": "x",
    })
    assert r.status_code == 201, r.text
    assert r.json()["customer_id"] == cid1
    assert r.json()["asset_id"] == aid2


def test_order_rejects_unknown_asset(client: TestClient) -> None:
    h = _login(client)
    cid1, _ = _customer_and_asset(client, h, "0888111222")
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid1, "asset_id": "00000000-0000-0000-0000-000000000000",
        "complaint": "x",
    })
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "not_found"


def test_status_transitions_ok_warn_no(client: TestClient) -> None:
    """order-workflow-revamp WP-G (Q1–Q4): received ("НОВА") only forwards to
    diagnostics/declined now — ready is no longer even a WARN skip from
    there, it's NO. diagnostics -> ready is where WARN now lives."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    order = _order(client, h, cid, aid)
    oid = order["id"]
    tech_id = _technician_id(client, h)

    # received -> diagnostics is OK (technician required — see
    # test_diagnostics_requires_a_technician below for that gate itself).
    r = client.post(f"/api/v1/orders/{oid}/status", headers=h,
                    json={"to": "diagnostics", "technician_id": tech_id})
    assert r.status_code == 200
    assert r.json()["status_code"] == "diagnostics"

    # diagnostics -> ready is WARN (skip allowed, warning surfaces).
    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "ready"})
    assert r.status_code == 200
    assert r.json()["warning"] == "skip"
    assert r.json()["status_code"] == "ready"

    # ready -> diagnostics is NO per the matrix (not even backward — ready's
    # only backward target is repair).
    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.orders.invalid_transition"


def test_diagnostics_requires_a_technician(client: TestClient) -> None:
    """order-workflow-revamp WP-G (Q2a)."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    assert r.status_code == 400
    assert r.json()["detail"]["message_key"] == "errors.orders.technician_required"

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h,
                    json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    assert r.status_code == 200
    assert r.json()["status_code"] == "diagnostics"


def test_diagnostics_succeeds_with_a_technician_already_set_at_intake(
    client: TestClient,
) -> None:
    """order-workflow-revamp WP-G (Q2b): ПРИЕМИ doesn't have to resend
    `technician_id` when intake already picked one — the precondition reads
    `order.technician_id`, not just the request body."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    tech_id = _technician_id(client, h)
    oid = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x", "technician_id": tech_id,
    }).json()["id"]

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    assert r.status_code == 200


def test_backward_transition_requires_reason(client: TestClient) -> None:
    """order-workflow-revamp WP-G (Q3/Q3b)."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "repair"})

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    assert r.status_code == 400
    assert r.json()["detail"]["message_key"] == "errors.orders.reason_required"

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h, json={
        "to": "diagnostics", "reason": "Оказа се друг проблем",
    })
    assert r.status_code == 200
    assert r.json()["status_code"] == "diagnostics"

    events = [e["event_type"] for e in client.get(f"/api/v1/orders/{oid}/timeline").json()]
    # One each for ->diagnostics, ->repair, and the final ->diagnostics
    # backward move — the failed 400 attempt above logged nothing.
    assert events.count("status_changed") == 3


def test_unrepairable_only_reachable_from_diagnostics(client: TestClient) -> None:
    """order-workflow-revamp WP-G (Q4)."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h,
                    json={"to": "unrepairable", "reason": "x"})
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.orders.invalid_transition"

    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    r = client.post(f"/api/v1/orders/{oid}/status", headers=h,
                    json={"to": "unrepairable", "reason": "Шасито е пропукано"})
    assert r.status_code == 200
    assert r.json()["status_kind"] == "terminal_failure"


def test_waiting_customer_requires_recorded_approval(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
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
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
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
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "repair"})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "ready"})

    r = client.post(f"/api/v1/orders/{oid}/status", headers=h,
                    json={"to": "completed", "warranty_days": 90})
    assert r.status_code == 200
    body = r.json()
    assert body["status_code"] == "completed"
    assert body["warranty_days"] == 90
    assert body["completed_at"] is not None


def test_cancelled_is_owner_only(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]

    from business_os.identity import security
    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

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
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
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
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    for to in ("repair", "ready"):
        client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": to})
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "completed"})

    r = client.post(f"/api/v1/orders/{oid}/warranty-return", headers=h,
                    json={"complaint": "Отново не се включва"})
    assert r.status_code == 201
    new_order = r.json()
    assert new_order["id"] != oid
    assert new_order["origin_order_id"] == oid
    assert new_order["status_code"] == "received"

    # The original stays terminal and untouched.
    original = client.get(f"/api/v1/orders/{oid}").json()
    assert original["status_code"] == "completed"


def test_warranty_return_requires_completed_source(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]
    r = client.post(f"/api/v1/orders/{oid}/warranty-return", headers=h,
                    json={"complaint": "x"})
    assert r.status_code == 409


def test_timeline_records_actor_and_survives_pin_switch(client: TestClient) -> None:
    from business_os.identity import security
    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)["id"]
    tech_id = _technician_id(client, h)

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

    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": tech_id})
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


# --- Wave 3 Issues 21/26/27: mileage + vehicle service history -------------

def _vehicle_customer_and_asset(client: TestClient, h: dict[str, str],
                                phone: str = "0888111222", vin: str | None = None,
                                ) -> tuple[str, str]:
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": phone}).json()["id"]
    field_values: dict[str, object] = {"brand": "Volkswagen", "model": "Golf"}
    if vin:
        field_values["vin"] = vin
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle", "field_values": field_values,
    }).json()["id"]
    return cid, aid


def test_order_accepts_mileage_for_any_asset_type(client: TestClient) -> None:
    """Not required/enforced by asset_type at the API layer (the frontend
    decides when to show the field) — a non-vehicle order may carry it too."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)  # "phone" asset type
    order = _order(client, h, cid, aid)
    assert order["mileage"] is None
    # WP-D (Q6): close the first before opening a second against the same asset.
    client.post(f"/api/v1/orders/{order['id']}/status", headers=h,
               json={"to": "declined", "reason": "Тест"})

    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x", "mileage": 100,
    })
    assert r.status_code == 201, r.text
    assert r.json()["mileage"] == 100


def test_order_rejects_negative_mileage(client: TestClient) -> None:
    h = _login(client, business_profile="automotive_repair")
    cid, aid = _vehicle_customer_and_asset(client, h)
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x", "mileage": -1,
    })
    assert r.status_code == 400


def test_vehicle_service_history_spans_ownership_change(client: TestClient) -> None:
    h = _login(client, business_profile="automotive_repair")
    cid1, aid = _vehicle_customer_and_asset(client, h, "0888111222", "WVWZZZ1JZ3W386752")
    cid2 = client.post("/api/v1/customers", headers=h,
                       json={"name": "Петър", "phone": "0888333444"}).json()["id"]

    order1 = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid1, "asset_id": aid, "complaint": "Смяна на масло",
        "mileage": 100000,
    }).json()

    client.post(f"/api/v1/assets/{aid}/transfer-owner", headers=h, json={"customer_id": cid2})
    # WP-D (Q6): close order1 before opening order2 against the same asset —
    # history still includes both regardless of status (list_orders_for_asset
    # is status-agnostic), so this doesn't weaken what's being verified below.
    client.post(f"/api/v1/orders/{order1['id']}/status", headers=h,
               json={"to": "declined", "reason": "Тест"})

    order2 = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid2, "asset_id": aid, "complaint": "Спирачки", "mileage": 105000,
    }).json()

    r = client.get(f"/api/v1/assets/{aid}/service-history", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current_mileage"] == 105000
    visit_ids = {v["order_id"] for v in body["visits"]}
    assert visit_ids == {order1["id"], order2["id"]}
    # Newest first.
    assert body["visits"][0]["order_id"] == order2["id"]
    assert body["visits"][0]["customer_id"] == cid2
    assert body["visits"][1]["customer_id"] == cid1


def _seed_vehicle_type_without_automotive_mileage_gate(email: str) -> None:
    """This test needs a "vehicle"-coded asset type to exist, but must NOT
    flip the company to automotive_repair — that profile requires mileage
    at order creation (Cleanup batch Issue 26), which would defeat the
    whole point of this test (an order with no mileage at all, relying on
    the service-history endpoint's fallback to the asset's own legacy
    field_values). AssetType.business_profile is just a descriptive tag on
    the row — only `companies.settings.repairflow.business_profile`
    (untouched here) drives the mileage gate, so seeding the type alone,
    without `set_business_profile`, is safe."""
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.assets.models import AssetType
    from serviceflow.assets.service import seed_default_types

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == email))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        already = db.scalar(select(AssetType).where(
            AssetType.company_id == owner.company_id, AssetType.code == "vehicle",
        ))
        if already is None:
            seed_default_types(db, owner.company_id, "automotive_repair")
        db.commit()


def test_vehicle_service_history_falls_back_to_legacy_asset_mileage(client: TestClient) -> None:
    h = _login(client)
    _seed_vehicle_type_without_automotive_mileage_gate("a@a.bg")
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": "0888111222"}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "Volkswagen", "model": "Golf", "mileage": 50000},
    }).json()["id"]
    client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Оглед",
    })

    r = client.get(f"/api/v1/assets/{aid}/service-history", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["current_mileage"] == 50000
    assert body["visits"][0]["mileage"] is None


def test_vehicle_service_history_prefers_order_mileage_over_legacy(client: TestClient) -> None:
    h = _login(client, business_profile="automotive_repair")
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": "0888111222"}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "Volkswagen", "model": "Golf", "mileage": 50000},
    }).json()["id"]
    client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Смяна на масло", "mileage": 51500,
    })

    body = client.get(f"/api/v1/assets/{aid}/service-history", headers=h).json()
    assert body["current_mileage"] == 51500


def test_vehicle_service_history_is_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg", business_profile="automotive_repair")
    _, aid = _vehicle_customer_and_asset(client, h_a)
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    assert client.get(f"/api/v1/assets/{aid}/service-history").status_code == 404


# --- Wave 5 Issue 12: order-level delivery method/address ------------------

def test_pickup_order_works_without_delivery_address(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x",
        "delivery_method": "pickup",
    })
    assert r.status_code == 201, r.text
    assert r.json()["delivery_method"] == "pickup"
    assert r.json()["delivery_address"] is None


def test_order_defaults_to_no_delivery_method_when_omitted(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    order = _order(client, h, cid, aid)
    assert order["delivery_method"] is None
    assert order["delivery_address"] is None


def test_courier_order_stores_its_own_explicit_delivery_address(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x",
        "delivery_method": "courier",
        "delivery_address": {"address": "ул. Куриерска 1"},
    })
    assert r.status_code == 201, r.text
    assert r.json()["delivery_method"] == "courier"
    assert r.json()["delivery_address"] == {"address": "ул. Куриерска 1"}


def test_courier_order_prefills_from_customer_default_delivery_address(
    client: TestClient,
) -> None:
    h = _login(client)
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Иван", "phone": "0888111222",
        "delivery_address": {"address": "адрес по подразбиране"},
    }).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]

    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x", "delivery_method": "courier",
    })
    assert r.status_code == 201, r.text
    assert r.json()["delivery_address"] == {"address": "адрес по подразбиране"}


def test_courier_order_explicit_address_overrides_customer_default(client: TestClient) -> None:
    h = _login(client)
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Иван", "phone": "0888111222",
        "delivery_address": {"address": "адрес по подразбиране"},
    }).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]

    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x", "delivery_method": "courier",
        "delivery_address": {"address": "адрес за конкретната поръчка"},
    })
    assert r.status_code == 201
    assert r.json()["delivery_address"] == {"address": "адрес за конкретната поръчка"}


def test_order_delivery_address_is_independent_of_later_customer_address_edits(
    client: TestClient,
) -> None:
    h = _login(client)
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Иван", "phone": "0888111222",
        "delivery_address": {"address": "стар адрес"},
    }).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]
    oid = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x", "delivery_method": "courier",
    }).json()["id"]

    client.patch(f"/api/v1/customers/{cid}", headers=h, json={
        "delivery_address": {"address": "нов адрес"},
    })

    order_after = client.get(f"/api/v1/orders/{oid}", headers=h).json()
    assert order_after["delivery_address"] == {"address": "стар адрес"}


def test_pickup_order_ignores_customer_default_address(client: TestClient) -> None:
    h = _login(client)
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Иван", "phone": "0888111222",
        "delivery_address": {"address": "адрес по подразбиране"},
    }).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]

    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x", "delivery_method": "pickup",
    })
    assert r.status_code == 201
    assert r.json()["delivery_address"] is None


def test_invalid_delivery_method_is_rejected(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x",
        "delivery_method": "drone",
    })
    assert r.status_code == 400


def test_payment_method_is_unaffected_by_delivery_method(client: TestClient) -> None:
    """Payment.method and ServiceOrder.delivery_method are independent —
    creating a courier order must not change payment behavior at all."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x",
        "delivery_method": "courier", "delivery_address": {"address": "адрес"},
    }).json()["id"]

    payment = client.post(f"/api/v1/orders/{oid}/payments", headers=h,
                          json={"amount": "10.00", "method": "cash", "note": ""})
    assert payment.status_code == 201, payment.text
    assert payment.json()["method"] == "cash"


# --- WP-F: technician load for the technician picker -----------------------

def _technicians(client: TestClient, h: dict[str, str]) -> tuple[str, str]:
    """(owner id, a new worker's id) — both are valid picker entries (Q22)."""
    owner = next(u["id"] for u in client.get("/api/v1/users").json() if u["is_owner"])
    worker = client.post("/api/v1/users", headers=h, json={
        "name": "Иво Иванов", "email": "ivo@a.bg", "password": "парола-за-иво-123",
    })
    assert worker.status_code == 201, worker.text
    return owner, worker.json()["id"]


def _order_in(client: TestClient, h: dict[str, str], cid: str,
              technician_id: str | None, path: list[str]) -> None:
    # WP-D (Q6): an asset can have at most one open order — every call here
    # creates its own asset to have several technicians' orders open at
    # once, exactly as separate customers' separate devices really would.
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple 13"},
    }).json()["id"]
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x",
        "technician_id": technician_id,
    })
    assert r.status_code == 201, r.text
    for to in path:
        s = client.post(f"/api/v1/orders/{r.json()['id']}/status", headers=h, json={"to": to})
        assert s.status_code == 200, s.text


def test_technician_load_counts_only_diagnostics_and_repair(client: TestClient) -> None:
    h = _login(client)
    owner, worker = _technicians(client, h)
    cid, _aid = _customer_and_asset(client, h)
    _order_in(client, h, cid, owner, ["diagnostics"])
    _order_in(client, h, cid, owner, ["diagnostics"])
    _order_in(client, h, cid, owner, ["diagnostics", "repair"])
    _order_in(client, h, cid, worker, ["diagnostics", "waiting_parts"])
    _order_in(client, h, cid, worker, [])  # Приета
    # order-workflow-revamp WP-G (Q2a): an order can no longer *reach*
    # diagnostics unassigned at all — technician-required is now a hard
    # precondition — so there's nothing left to exercise for "an unassigned
    # order in diagnostics doesn't count" specifically; the stays-"Приета"
    # case right above already proves an order with no technician
    # contributes nothing to the load count (TECHNICIAN_LOAD never includes
    # "received" either way).

    r = client.get("/api/v1/orders/technician-load")
    assert r.status_code == 200, r.text
    assert r.json() == [{"technician_id": owner, "active_count": 3}]


def test_technician_load_is_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    owner_a = next(u["id"] for u in client.get("/api/v1/users").json() if u["is_owner"])
    cid, _aid = _customer_and_asset(client, h_a)
    _order_in(client, h_a, cid, owner_a, ["diagnostics"])
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    r = client.get("/api/v1/orders/technician-load")
    assert r.status_code == 200, r.text
    assert r.json() == []
