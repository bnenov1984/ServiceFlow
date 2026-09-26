"""Invoice-order linking (invoice-order-linking checkpoint 1): POST
/invoices/{invoice_id}/link-order attaches an existing manual invoice
(order_id IS NULL, created via POST /invoices) to a ServiceOrder after the
fact — a new relationship, distinct from the reissue-only annuls_invoice_id
field. See commercial/service.py's `link_to_order()`."""

import os
import uuid as uuid_mod

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)

VALID_EIK = "130489869"


def _login(client: TestClient, company: str = "Сервиз А",
          email: str = "a@a.bg") -> dict[str, str]:
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, company, "Owner", email, "парола-123")
    me = client.post("/api/v1/auth/login",
                     json={"email": email, "password": "парола-123"}).json()
    return {"X-CSRF-Token": str(me["csrf_token"])}


def _ready_seller(client: TestClient, h: dict[str, str], eik: str = VALID_EIK) -> None:
    resp = client.patch("/api/v1/company/requisites", headers=h,
                        json={"address": "гр. София, ул. Примерна 1", "eik": eik})
    assert resp.status_code == 200, resp.text


def _customer(client: TestClient, h: dict[str, str], *, name: str = "Иван Петров") -> str:
    resp = client.post("/api/v1/customers", headers=h,
                       json={"name": name, "phone": "0888111222"})
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _manual_draft(client: TestClient, h: dict[str, str], customer_id: str) -> str:
    resp = client.post("/api/v1/invoices", headers=h, json={"customer_id": customer_id})
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _order(client: TestClient, h: dict[str, str], customer_id: str,
          complaint: str = "Тест") -> str:
    aid = client.post(f"/api/v1/customers/{customer_id}/assets", headers=h, json={
        "asset_type_code": "phone", "field_values": {"brand": "Apple"},
    }).json()["id"]
    resp = client.post("/api/v1/orders", headers=h, json={
        "customer_id": customer_id, "asset_id": aid, "complaint": complaint,
    })
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _link(client: TestClient, h: dict[str, str], invoice_id: str, order_id: str) -> "object":
    return client.post(f"/api/v1/invoices/{invoice_id}/link-order", headers=h,
                       json={"order_id": order_id})


# --- Success ------------------------------------------------------------


def test_manual_invoice_can_be_linked_to_an_order_of_the_same_customer(
    client: TestClient,
) -> None:
    h = _login(client)
    cid = _customer(client, h)
    invoice_id = _manual_draft(client, h, cid)
    order_id = _order(client, h, cid)

    resp = _link(client, h, invoice_id, order_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order_id"] == order_id
    # customer_id is intentionally left set, not cleared, once linked.
    assert body["customer_id"] == cid


def test_linking_bumps_row_version(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    invoice_id = _manual_draft(client, h, cid)
    order_id = _order(client, h, cid)
    before = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()["row_version"]

    resp = _link(client, h, invoice_id, order_id)
    assert resp.json()["row_version"] == before + 1


def test_linked_manual_invoice_appears_in_the_orders_own_invoice_list(
    client: TestClient,
) -> None:
    h = _login(client)
    cid = _customer(client, h)
    invoice_id = _manual_draft(client, h, cid)
    order_id = _order(client, h, cid)
    _link(client, h, invoice_id, order_id)

    body = client.get(f"/api/v1/invoices?order_id={order_id}", headers=h).json()
    assert [r["id"] for r in body] == [invoice_id]


def test_an_already_issued_manual_invoice_can_be_linked_too(client: TestClient) -> None:
    """Linking sets a reference only, never touches financial content — an
    issued invoice's immutability (root CLAUDE.md rule 6) is unaffected."""
    h = _login(client)
    _ready_seller(client, h)
    cid = _customer(client, h)
    invoice_id = _manual_draft(client, h, cid)
    client.patch(f"/api/v1/invoices/{invoice_id}", headers=h, json={
        "lines": [{"description": "Диагностика", "qty": 1, "unit_price": "30",
                  "source": "manual"}],
    })
    issued = client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=h,
                         json={"tax_event_date": "2026-03-15"})
    assert issued.status_code == 200, issued.text
    frozen_gross = issued.json()["gross"]
    order_id = _order(client, h, cid)

    resp = _link(client, h, invoice_id, order_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order_id"] == order_id
    assert body["status"] == "issued"
    assert body["gross"] == frozen_gross  # unchanged by linking


def test_timeline_event_recorded_on_the_linked_order(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    invoice_id = _manual_draft(client, h, cid)
    order_id = _order(client, h, cid)

    _link(client, h, invoice_id, order_id)

    events = client.get(f"/api/v1/orders/{order_id}/timeline", headers=h).json()
    types = [e["event_type"] for e in events]
    assert "invoice_linked" in types


# --- Rejections -----------------------------------------------------------


def test_reject_if_invoice_not_found(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    order_id = _order(client, h, cid)

    resp = _link(client, h, str(uuid_mod.uuid4()), order_id)
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.invoices.not_found"


def test_reject_if_order_not_found(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    invoice_id = _manual_draft(client, h, cid)

    resp = _link(client, h, invoice_id, str(uuid_mod.uuid4()))
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.orders.not_found"


def test_reject_if_already_linked(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    invoice_id = _manual_draft(client, h, cid)
    order_id = _order(client, h, cid)
    _link(client, h, invoice_id, order_id)
    other_order_id = _order(client, h, cid, complaint="Втора поръчка")

    resp = _link(client, h, invoice_id, other_order_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.already_linked"


def test_reject_linking_an_order_generated_invoice(client: TestClient) -> None:
    """An order-generated invoice already has order_id set at creation —
    link-order is for manual invoices only, never a re-link."""
    h = _login(client)
    _ready_seller(client, h)
    cid = _customer(client, h)
    order_id = _order(client, h, cid)
    order_invoice_id = client.post(f"/api/v1/orders/{order_id}/invoices", headers=h).json()["id"]
    other_order_id = _order(client, h, cid, complaint="Друга поръчка")

    resp = _link(client, h, order_invoice_id, other_order_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.already_linked"


def test_reject_if_customer_mismatch(client: TestClient) -> None:
    h = _login(client)
    cid_invoice = _customer(client, h, name="Клиент А")
    cid_order = _customer(client, h, name="Клиент Б")
    invoice_id = _manual_draft(client, h, cid_invoice)
    order_id = _order(client, h, cid_order)

    resp = _link(client, h, invoice_id, order_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.customer_mismatch"


def test_reject_if_order_archived(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    invoice_id = _manual_draft(client, h, cid)
    order_id = _order(client, h, cid)
    cancel_resp = client.post(f"/api/v1/orders/{order_id}/status", headers=h,
                              json={"to": "cancelled", "reason": "Тест архивиране"})
    assert cancel_resp.status_code == 200, cancel_resp.text
    archive_resp = client.post(f"/api/v1/orders/{order_id}/archive", headers=h)
    assert archive_resp.status_code == 200, archive_resp.text

    resp = _link(client, h, invoice_id, order_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.orders.archived"


def test_cross_tenant_order_rejected_as_not_found(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    cid_a = _customer(client, h_a)
    invoice_id = _manual_draft(client, h_a, cid_a)
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    cid_b = _customer(client, h_b)
    order_id_b = _order(client, h_b, cid_b)
    client.post("/api/v1/auth/logout", headers=h_b)

    h_a2 = _login(client, "Сервиз А", "a@a.bg")
    resp = _link(client, h_a2, invoice_id, order_id_b)
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.orders.not_found"


# --- Permissions / CSRF (Worker may link, same tier as patch/create) -------


def test_worker_may_link_a_manual_invoice(client: TestClient) -> None:
    h_owner = _login(client)
    cid = _customer(client, h_owner)
    invoice_id = _manual_draft(client, h_owner, cid)
    order_id = _order(client, h_owner, cid)
    client.post("/api/v1/users", headers=h_owner,
               json={"name": "Иво", "email": "ivo@a.bg", "password": "парола-за-иво-123"})
    client.post("/api/v1/auth/logout", headers=h_owner)

    me = client.post("/api/v1/auth/login",
                     json={"email": "ivo@a.bg", "password": "парола-за-иво-123"}).json()
    h_worker = {"X-CSRF-Token": str(me["csrf_token"])}
    resp = _link(client, h_worker, invoice_id, order_id)
    assert resp.status_code == 200, resp.text


def test_missing_csrf_forbidden(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    invoice_id = _manual_draft(client, h, cid)
    order_id = _order(client, h, cid)

    resp = client.post(f"/api/v1/invoices/{invoice_id}/link-order", json={"order_id": order_id})
    assert resp.status_code == 403
    assert resp.json()["detail"]["message_key"] == "errors.auth.csrf"
