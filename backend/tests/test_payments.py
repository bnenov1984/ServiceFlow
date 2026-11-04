"""Payment recording (docs/01 §Payment): unified deposit/partial/refund
mechanism, always outside the ServiceOrder aggregate (docs/01 §4). Money
totals stay derived (BR-3) — no stored paid flag."""

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


def _catalog_item(client: TestClient, h: dict[str, str], *, kind: str = "labor",
                  name: str = "Труд", sale_price: str = "100.00") -> str:
    r = client.post("/api/v1/catalog-items", headers=h,
                    json={"kind": kind, "name": name, "unit": "pcs", "sale_price": sale_price})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def _order_with_total(client: TestClient, h: dict[str, str], total: str) -> str:
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    item_id = _catalog_item(client, h, sale_price=total)
    client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
               json={"catalog_item_id": item_id})
    return oid


def test_normal_payment_is_recorded(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)

    r = client.post(f"/api/v1/orders/{oid}/payments", headers=h, json={
        "amount": "50.00", "method": "cash",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["amount"] == 50.0
    assert body["method"] == "cash"
    assert body["is_refund"] is False
    assert body["invoice_id"] is None


@pytest.mark.parametrize("method", ["cash", "card", "bank"])
def test_all_payment_methods_accepted(client: TestClient, method: str) -> None:
    h = _login(client)
    oid = _order(client, h)
    r = client.post(f"/api/v1/orders/{oid}/payments", headers=h,
                    json={"amount": "10.00", "method": method})
    assert r.status_code == 201
    assert r.json()["method"] == method


def test_invalid_method_rejected(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    r = client.post(f"/api/v1/orders/{oid}/payments", headers=h,
                    json={"amount": "10.00", "method": "paypal"})
    assert r.status_code == 400


@pytest.mark.parametrize("amount", ["0", "-5.00"])
def test_zero_or_negative_amount_rejected(client: TestClient, amount: str) -> None:
    h = _login(client)
    oid = _order(client, h)
    r = client.post(f"/api/v1/orders/{oid}/payments", headers=h,
                    json={"amount": amount, "method": "cash"})
    assert r.status_code == 400
    assert r.json()["message_key"] == "errors.validation"


def test_refund_is_a_separate_offsetting_record_not_a_mutation(client: TestClient) -> None:
    h = _login(client)
    oid = _order_with_total(client, h, "100.00")

    p1 = client.post(f"/api/v1/orders/{oid}/payments", headers=h,
                     json={"amount": "100.00", "method": "cash"}).json()
    p2 = client.post(f"/api/v1/orders/{oid}/payments", headers=h, json={
        "amount": "30.00", "method": "cash", "is_refund": True, "note": "връщане",
    }).json()

    # Two distinct, positive-amount records — the refund never carries a
    # negative amount, and the original payment is untouched.
    assert p1["id"] != p2["id"]
    assert p1["amount"] == 100.0
    assert p2["amount"] == 30.0
    assert p2["is_refund"] is True

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["paid_amount"] == 70.0
    assert detail["balance"] == 30.0


def test_paid_amount_and_balance_with_multiple_payments(client: TestClient) -> None:
    h = _login(client)
    oid = _order_with_total(client, h, "200.00")

    client.post(f"/api/v1/orders/{oid}/payments", headers=h,
               json={"amount": "80.00", "method": "cash"})
    client.post(f"/api/v1/orders/{oid}/payments", headers=h,
               json={"amount": "70.00", "method": "card"})

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["estimated_total"] == 200.0
    assert detail["paid_amount"] == 150.0
    assert detail["balance"] == 50.0


def test_balance_reuses_canonical_order_total(client: TestClient) -> None:
    """balance must equal the same total GET /orders/{id} already reports as
    estimated_total (lines.order_totals) — not a second money formula."""
    h = _login(client)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": "diagnostics"})
    part_id = _catalog_item(client, h, kind="part", name="Дисплей", sale_price="100")
    labor_id = _catalog_item(client, h, kind="labor", name="Труд", sale_price="50")
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"catalog_item_id": part_id})
    client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
               json={"catalog_item_id": labor_id})
    client.post(f"/api/v1/orders/{oid}/payments", headers=h,
               json={"amount": "40.00", "method": "cash"})

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["estimated_total"] == 150.0
    assert detail["balance"] == detail["estimated_total"] - detail["paid_amount"]


def test_overpayment_allowed_and_yields_negative_balance(client: TestClient) -> None:
    """Nothing in docs/01 forbids paying more than the total (e.g. change
    given in cash); balance is allowed to go negative (credit)."""
    h = _login(client)
    oid = _order_with_total(client, h, "50.00")
    client.post(f"/api/v1/orders/{oid}/payments", headers=h,
               json={"amount": "80.00", "method": "cash"})

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["paid_amount"] == 80.0
    assert detail["balance"] == -30.0


def test_payment_and_refund_emit_timeline_events(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/payments", headers=h,
               json={"amount": "50.00", "method": "cash"})
    client.post(f"/api/v1/orders/{oid}/payments", headers=h,
               json={"amount": "20.00", "method": "cash", "is_refund": True})

    events = [e["event_type"] for e in client.get(f"/api/v1/orders/{oid}/timeline").json()]
    assert "payment_recorded" in events
    assert "payment_refunded" in events


def test_payment_allowed_on_terminal_order(client: TestClient) -> None:
    """docs/01 §ServiceOrder invariants: terminal orders accept payments
    settling an outstanding balance — the one operational exception."""
    h = _login(client)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "cancelled", "reason": "дубликат"})

    r = client.post(f"/api/v1/orders/{oid}/payments", headers=h,
                    json={"amount": "10.00", "method": "cash"})
    assert r.status_code == 201


def test_payment_rejected_on_archived_order(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "cancelled", "reason": "дубликат"})
    client.post(f"/api/v1/orders/{oid}/archive", headers=h)

    r = client.post(f"/api/v1/orders/{oid}/payments", headers=h,
                    json={"amount": "10.00", "method": "cash"})
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.orders.archived"


def test_payment_on_nonexistent_order_returns_404(client: TestClient) -> None:
    h = _login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(f"/api/v1/orders/{fake_id}/payments", headers=h,
                    json={"amount": "10.00", "method": "cash"})
    assert r.status_code == 404
    assert r.json()["detail"]["message_key"] == "errors.orders.not_found"


def test_cross_tenant_order_cannot_receive_payment(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid = _order(client, h_a)
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    r = client.post(f"/api/v1/orders/{oid}/payments", headers=h_b,
                    json={"amount": "10.00", "method": "cash"})
    assert r.status_code == 404


def test_cross_tenant_order_detail_hides_other_companys_payments(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid = _order(client, h_a)
    client.post(f"/api/v1/orders/{oid}/payments", headers=h_a,
               json={"amount": "10.00", "method": "cash"})
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    assert client.get(f"/api/v1/orders/{oid}").status_code == 404


def test_rls_blocks_even_unscoped_payment_queries(client: TestClient) -> None:
    """ADR-016 layer 3: a raw query that FORGETS scoped() still cannot cross
    tenants (mirrors test_customers.py::test_rls_blocks_even_unscoped_queries)."""
    from sqlalchemy import select, text

    from business_os.shared_kernel.db import open_session
    from serviceflow.commercial.models import Payment

    h = _login(client, "Сервиз А", "a@a.bg")
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/payments", headers=h,
               json={"amount": "10.00", "method": "cash"})

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    for db in open_session(url):
        # No GUC set → fail closed: zero rows even without any WHERE clause.
        assert db.scalars(select(Payment)).all() == []

        # GUC set to a random other company → still zero rows.
        db.execute(text(
            "SELECT set_config('app.company_id',"
            " '00000000-0000-0000-0000-000000000000', false)"
        ))
        assert db.scalars(select(Payment)).all() == []
