"""order-workflow-revamp WP-D (Q6/Q6b): a new order is blocked for an asset
that already has one open — every non-terminal status, including "ready"
("Готова") — regardless of asset type. Enforced in
serviceflow.service_orders.service.create() (shared by every caller,
including warranty_return()); GET /assets/{id}/open-order is the read-only
asset-step pre-check backing the intake-time block."""

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


def _customer_and_asset(client: TestClient, h: dict[str, str],
                        phone: str = "0888111222") -> tuple[str, str]:
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": phone}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Самсунг телевизор"},
    }).json()["id"]
    return cid, aid


def _order(client: TestClient, h: dict[str, str], cid: str, aid: str,
          complaint: str = "x") -> dict[str, object]:
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": complaint,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _transition(client: TestClient, h: dict[str, str], order_id: str, to: str) -> None:
    # terminal_failure transitions (declined/unrepairable/cancelled) require
    # a reason; harmless to always send one.
    r = client.post(f"/api/v1/orders/{order_id}/status", headers=h,
                    json={"to": to, "reason": "Тест"})
    assert r.status_code == 200, r.text


def _to_completed(client: TestClient, h: dict[str, str], order_id: str) -> None:
    for to in ("diagnostics", "repair", "ready", "completed"):
        _transition(client, h, order_id, to)


# --- Block on create ----------------------------------------------------------


def test_second_order_for_same_asset_blocked_while_first_is_open(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    first = _order(client, h, cid, aid)

    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Втори проблем",
    })
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.orders.open_order_exists"
    assert r.json()["detail"]["params"]["number"] == first["number"]


def test_ready_status_still_counts_as_open(client: TestClient) -> None:
    """Q6: "Готова" is explicitly non-terminal for this rule — a car waiting
    for pickup still blocks a new order."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    first = _order(client, h, cid, aid)
    for to in ("diagnostics", "repair", "ready"):
        _transition(client, h, first["id"], to)

    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Втори проблем",
    })
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.orders.open_order_exists"


@pytest.mark.parametrize("terminal_to", ["declined", "unrepairable", "cancelled"])
def test_new_order_allowed_once_prior_is_terminal(client: TestClient, terminal_to: str) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    first = _order(client, h, cid, aid)
    _transition(client, h, first["id"], terminal_to)

    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Втори проблем",
    })
    assert r.status_code == 201, r.text


def test_block_applies_to_every_asset_type_not_just_vehicles(client: TestClient) -> None:
    """The fixture asset here is already "other" (non-vehicle) — this test
    exists to make that scope explicit, not incidental."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    _order(client, h, cid, aid)

    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Втори проблем",
    })
    assert r.status_code == 409


def test_open_order_for_a_different_asset_does_not_block(client: TestClient) -> None:
    h = _login(client)
    cid, aid1 = _customer_and_asset(client, h)
    _, aid2 = _customer_and_asset(client, h, phone="0888333444")
    _order(client, h, cid, aid1)

    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid2, "complaint": "Друг актив",
    })
    assert r.status_code == 201, r.text


def test_does_not_consume_an_order_number_when_blocked(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    first = _order(client, h, cid, aid)

    blocked = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Втори проблем",
    })
    assert blocked.status_code == 409
    _transition(client, h, first["id"], "declined")

    second = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Трети проблем",
    })
    assert second.status_code == 201, second.text
    year = str(__import__("datetime").date.today().year)
    # first=00001, blocked attempt never allocated a number, second=00002.
    assert second.json()["number"] == f"{year}-00002"


# --- Warranty returns (Q6: "unaffected — original must be completed") -------


def test_warranty_return_allowed_when_asset_has_no_other_open_order(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    original = _order(client, h, cid, aid)
    _to_completed(client, h, original["id"])

    r = client.post(f"/api/v1/orders/{original['id']}/warranty-return", headers=h,
                    json={"complaint": "Отново не работи"})
    assert r.status_code == 201, r.text


def test_warranty_return_blocked_when_asset_has_a_separate_open_order(client: TestClient) -> None:
    """The ORIGINAL being completed doesn't block its own warranty return
    (it's terminal, not open) — but a *different*, still-open order against
    the same asset does, via the same shared create() check."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    original = _order(client, h, cid, aid)
    _to_completed(client, h, original["id"])
    concurrent = _order(client, h, cid, aid)  # a fresh, unrelated open order

    r = client.post(f"/api/v1/orders/{original['id']}/warranty-return", headers=h,
                    json={"complaint": "Отново не работи"})
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.orders.open_order_exists"
    assert r.json()["detail"]["params"]["number"] == concurrent["number"]


# --- GET /assets/{id}/open-order (Q6b pre-check) -----------------------------


def test_open_order_check_reports_the_open_order(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    order = _order(client, h, cid, aid)

    r = client.get(f"/api/v1/assets/{aid}/open-order", headers=h)
    assert r.status_code == 200
    assert r.json() == {
        "order_id": order["id"], "number": order["number"], "status_code": "received",
    }


def test_open_order_check_reports_none_when_clear(client: TestClient) -> None:
    h = _login(client)
    _, aid = _customer_and_asset(client, h)

    r = client.get(f"/api/v1/assets/{aid}/open-order", headers=h)
    assert r.status_code == 200
    assert r.json() == {"order_id": None, "number": None, "status_code": None}


def test_open_order_check_is_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    cid, aid = _customer_and_asset(client, h_a)
    _order(client, h_a, cid, aid)
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    r = client.get(f"/api/v1/assets/{aid}/open-order")
    assert r.status_code == 404
