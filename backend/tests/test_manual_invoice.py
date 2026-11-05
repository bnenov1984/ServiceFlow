"""Manual Invoice creation (Wave 6 Issue 30, second half): POST /invoices
creates an order-less draft from a directly-supplied customer_id. Reuses
the exact same draft/replace-lines/issue/PDF/annul machinery every
order-generated invoice already uses — see commercial/service.py's
`create_manual_draft()` and `issue()`'s buyer-resolution fork."""

import os
import uuid as uuid_mod

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)

VALID_EIK = "130489869"
TAX_EVENT_DATE = "2026-03-15"


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


def _customer(client: TestClient, h: dict[str, str], *, name: str = "Иван Петров",
              phone: str = "0888111222") -> str:
    resp = client.post("/api/v1/customers", headers=h,
                       json={"name": name, "phone": phone})
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _technician_id(client: TestClient, h: dict[str, str]) -> str:
    """order-workflow-revamp WP-G (Q2a): diagnostics now requires a
    technician on file — the Owner is itself a valid one (Q22)."""
    return str(next(u["id"] for u in client.get("/api/v1/users", headers=h).json()
                    if u["is_owner"]))


def _manual_draft(client: TestClient, h: dict[str, str], customer_id: str) -> "object":
    return client.post("/api/v1/invoices", headers=h, json={"customer_id": customer_id})


def _add_line(client: TestClient, h: dict[str, str], invoice_id: str,
             description: str = "Диагностика", unit_price: str = "30") -> "object":
    return client.patch(f"/api/v1/invoices/{invoice_id}", headers=h, json={
        "lines": [{"description": description, "qty": 1, "unit_price": unit_price,
                  "source": "manual"}],
    })


def _issue(client: TestClient, h: dict[str, str], invoice_id: str,
          tax_event_date: str = TAX_EVENT_DATE) -> "object":
    return client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=h,
                       json={"tax_event_date": tax_event_date})


def _issued_manual_invoice(client: TestClient, h: dict[str, str], *,
                           customer_name: str = "Иван Петров") -> tuple[str, str]:
    """Returns (invoice_id, customer_id)."""
    _ready_seller(client, h)
    cid = _customer(client, h, name=customer_name)
    invoice_id = str(_manual_draft(client, h, cid).json()["id"])
    _add_line(client, h, invoice_id)
    r = _issue(client, h, invoice_id)
    assert r.status_code == 200, r.text
    return invoice_id, cid


# --- Draft creation ---------------------------------------------------------


def test_manual_draft_created_with_no_order_and_no_number(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)

    resp = _manual_draft(client, h, cid)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["order_id"] is None
    assert body["customer_id"] == cid
    assert body["status"] == "draft"
    assert body["number"] is None
    assert body["lines"] == []
    assert body["draft_total"] == 0.0


def test_manual_draft_does_not_create_a_service_order(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    _manual_draft(client, h, cid)

    resp = client.get("/api/v1/orders", headers=h)
    assert resp.status_code == 200
    assert resp.json() == []


def test_manual_draft_for_missing_customer_rejected(client: TestClient) -> None:
    h = _login(client)
    fake_id = str(uuid_mod.uuid4())
    resp = _manual_draft(client, h, fake_id)
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.invoices.customer_not_found"


def test_manual_draft_for_cross_tenant_customer_rejected(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    cid_a = _customer(client, h_a)
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    resp = _manual_draft(client, h_b, cid_a)
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.invoices.customer_not_found"


def test_manual_draft_lines_are_added_via_the_same_replace_lines_endpoint(
    client: TestClient,
) -> None:
    h = _login(client)
    cid = _customer(client, h)
    invoice_id = str(_manual_draft(client, h, cid).json()["id"])

    resp = _add_line(client, h, invoice_id, description="Диагностика", unit_price="30")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["lines"]) == 1
    assert body["lines"][0]["description"] == "Диагностика"
    assert body["draft_total"] == 30.0


# --- Issue: same engine, shared numbering -----------------------------------


def test_manual_invoice_issue_uses_selected_customer_as_buyer_snapshot(
    client: TestClient,
) -> None:
    h = _login(client)
    invoice_id, _ = _issued_manual_invoice(client, h, customer_name="Мария Иванова")

    body = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()
    assert body["buyer"] == {"name": "Мария Иванова"}


def test_manual_invoice_vat_and_totals_identical_to_order_invoice(client: TestClient) -> None:
    h = _login(client)
    client.patch("/api/v1/company/requisites", headers=h,
                json={"address": "гр. София, ул. Примерна 1", "eik": VALID_EIK,
                     "vat_registered": True})
    cid = _customer(client, h)
    invoice_id = str(_manual_draft(client, h, cid).json()["id"])
    _add_line(client, h, invoice_id, unit_price="100")

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["vat_mode"] == "registered"
    assert body["net"] == 100.0
    assert body["vat"] == 20.0
    assert body["gross"] == 120.0


def test_manual_invoice_requires_explicit_tax_event_date(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    cid = _customer(client, h)
    invoice_id = str(_manual_draft(client, h, cid).json()["id"])
    _add_line(client, h, invoice_id)

    resp = client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=h, json={})
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_manual_invoice_empty_draft_rejected_same_as_order_invoice(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    cid = _customer(client, h)
    invoice_id = str(_manual_draft(client, h, cid).json()["id"])

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.empty"


def test_manual_and_order_invoices_share_one_continuous_number_sequence(
    client: TestClient,
) -> None:
    h = _login(client)
    _ready_seller(client, h)

    # Order-generated invoice first.
    cid1 = _customer(client, h, name="Клиент А")
    aid = client.post(f"/api/v1/customers/{cid1}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]
    oid = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid1, "asset_id": aid, "complaint": "Тест",
    }).json()["id"]
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    labor_item_id = client.post("/api/v1/catalog-items", headers=h, json={
        "kind": "labor", "name": "Труд", "unit": "pcs", "sale_price": "20",
    }).json()["id"]
    client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
               json={"catalog_item_id": labor_item_id})
    order_invoice_id = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"]
    order_invoice_number = _issue(client, h, order_invoice_id).json()["number"]

    # Manual invoice second — must continue the SAME sequence, not a
    # separate one.
    cid2 = _customer(client, h, name="Клиент Б", phone="0888111333")
    manual_invoice_id = str(_manual_draft(client, h, cid2).json()["id"])
    _add_line(client, h, manual_invoice_id)
    manual_invoice_number = _issue(client, h, manual_invoice_id).json()["number"]

    assert manual_invoice_number == order_invoice_number + 1


def test_issued_manual_invoice_is_immutable(client: TestClient) -> None:
    h = _login(client)
    invoice_id, _ = _issued_manual_invoice(client, h)

    resp = client.patch(f"/api/v1/invoices/{invoice_id}", headers=h, json={
        "lines": [{"description": "опит за промяна", "qty": 1, "unit_price": "1",
                  "source": "manual"}],
    })
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.not_draft"


# --- PDF / annul -------------------------------------------------------------


def test_manual_invoice_pdf_available_after_issue(client: TestClient) -> None:
    h = _login(client)
    invoice_id, _ = _issued_manual_invoice(client, h)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


def test_manual_invoice_can_be_annulled(client: TestClient) -> None:
    h = _login(client)
    invoice_id, _ = _issued_manual_invoice(client, h)

    resp = client.post(f"/api/v1/invoices/{invoice_id}/annul", headers=h,
                       json={"reason": "Грешно избран клиент"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "annulled"


# --- Central list: visibility / order column / customer filter -------------


def test_manual_invoice_appears_in_central_list_with_null_order(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    invoice_id = str(_manual_draft(client, h, cid).json()["id"])

    body = client.get("/api/v1/invoices", headers=h).json()
    row = [r for r in body if r["id"] == invoice_id][0]
    assert row["order_id"] is None
    assert row["order_number"] is None
    assert row["customer_name"] == "Иван Петров"


def test_customer_id_filter_finds_manual_invoices(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    invoice_id = str(_manual_draft(client, h, cid).json()["id"])

    body = client.get(f"/api/v1/invoices?customer_id={cid}", headers=h).json()
    assert [r["id"] for r in body] == [invoice_id]


def test_customer_id_filter_still_finds_order_generated_invoices(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    cid = _customer(client, h)
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]
    oid = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Тест",
    }).json()["id"]
    order_invoice_id = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"]

    body = client.get(f"/api/v1/invoices?customer_id={cid}", headers=h).json()
    assert [r["id"] for r in body] == [order_invoice_id]


def test_customer_id_filter_combines_manual_and_order_invoices_for_same_customer(
    client: TestClient,
) -> None:
    h = _login(client)
    _ready_seller(client, h)
    cid = _customer(client, h)
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]
    oid = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Тест",
    }).json()["id"]
    order_invoice_id = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"]
    manual_invoice_id = str(_manual_draft(client, h, cid).json()["id"])

    body = client.get(f"/api/v1/invoices?customer_id={cid}", headers=h).json()
    assert {r["id"] for r in body} == {order_invoice_id, manual_invoice_id}


def test_order_id_filter_unaffected_by_manual_invoices(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    cid = _customer(client, h)
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]
    oid = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Тест",
    }).json()["id"]
    order_invoice_id = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"]
    _manual_draft(client, h, cid)  # a distractor manual invoice, same customer

    body = client.get(f"/api/v1/invoices?order_id={oid}", headers=h).json()
    assert [r["id"] for r in body] == [order_invoice_id]


# --- Permissions / CSRF / subscription (Worker may create drafts) ----------


def test_worker_may_create_a_manual_draft(client: TestClient) -> None:
    h_owner = _login(client)
    cid = _customer(client, h_owner)
    client.post("/api/v1/users", headers=h_owner,
               json={"name": "Иво", "email": "ivo@a.bg", "password": "парола-за-иво-123"})
    client.post("/api/v1/auth/logout", headers=h_owner)

    me = client.post("/api/v1/auth/login",
                     json={"email": "ivo@a.bg", "password": "парола-за-иво-123"}).json()
    h_worker = {"X-CSRF-Token": str(me["csrf_token"])}
    resp = _manual_draft(client, h_worker, cid)
    assert resp.status_code == 201, resp.text


def test_missing_csrf_forbidden(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    resp = client.post("/api/v1/invoices", json={"customer_id": cid})
    assert resp.status_code == 403
    assert resp.json()["detail"]["message_key"] == "errors.auth.csrf"
