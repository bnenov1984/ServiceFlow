"""Invoice drafts (docs/01 §Invoice): draft-only slice — creation prefilled
from an order's part/labor lines via service_orders' public contract, list,
detail, and draft line replacement. No issue/annul/reissue/PDF/VAT — those
are a later slice (see backend/src/serviceflow/commercial/models.py)."""

import itertools
import os

import pytest
from fastapi.testclient import TestClient

# order-workflow-revamp WP-B (Q7): a second individual customer with the
# same phone is now blocked, so `_order()` — called multiple times per test
# with no caller-supplied uniqueness — needs a phone that's guaranteed
# distinct on every call, never a fixed literal.
_phone_seq = itertools.count(100000)


def _unique_phone() -> str:
    return f"0888{next(_phone_seq)}"


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
                      json={"name": "Иван", "phone": _unique_phone()}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]
    return str(client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Не се включва",
    }).json()["id"])


def _order_with_lines(client: TestClient, h: dict[str, str]) -> str:
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"name": "Дисплей", "qty": 1, "unit_cost": "60", "unit_price": "100"})
    client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
               json={"description": "Смяна на дисплей", "qty": 1, "unit_price": "50"})
    return oid


def test_draft_prefilled_from_part_and_labor_lines(client: TestClient) -> None:
    h = _login(client)
    oid = _order_with_lines(client, h)

    r = client.post(f"/api/v1/orders/{oid}/invoices", headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "draft"
    assert body["order_id"] == oid
    assert body["number"] is None
    assert body["currency"] == "EUR"
    assert body["draft_total"] == 150.0

    sources = {line["source"] for line in body["lines"]}
    assert sources == {"part", "labor"}
    descriptions = {line["description"] for line in body["lines"]}
    assert descriptions == {"Дисплей", "Смяна на дисплей"}


def test_draft_created_empty_when_order_has_no_lines(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)

    r = client.post(f"/api/v1/orders/{oid}/invoices", headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["lines"] == []
    assert body["draft_total"] == 0.0


def test_draft_creation_on_nonexistent_order_returns_404(client: TestClient) -> None:
    h = _login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(f"/api/v1/orders/{fake_id}/invoices", headers=h)
    assert r.status_code == 404
    assert r.json()["detail"]["message_key"] == "errors.orders.not_found"


def test_draft_creation_rejected_on_archived_order(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "cancelled", "reason": "дубликат"})
    client.post(f"/api/v1/orders/{oid}/archive", headers=h)

    r = client.post(f"/api/v1/orders/{oid}/invoices", headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.orders.archived"


def test_draft_creation_allowed_on_terminal_order(client: TestClient) -> None:
    """Invoices are possible on terminal orders (e.g. diagnostic fee on a
    declined repair, docs/02 §11) — only archiving blocks it."""
    h = _login(client)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "cancelled", "reason": "дубликат"})

    r = client.post(f"/api/v1/orders/{oid}/invoices", headers=h)
    assert r.status_code == 201


def test_list_invoices_filters_by_status(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/invoices", headers=h)

    r = client.get("/api/v1/invoices?status=draft")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/v1/invoices?status=issued")
    assert r.status_code == 200
    assert r.json() == []


def test_list_invoices_filters_by_order_id(client: TestClient) -> None:
    """order_id is the frontend's way to answer "does this order already
    have a draft" without fetching the whole company's invoice list —
    additive query param, docs/09 §3 allows new optional fields freely."""
    h = _login(client)
    oid_a = _order(client, h)
    oid_b = _order(client, h)
    client.post(f"/api/v1/orders/{oid_a}/invoices", headers=h)
    client.post(f"/api/v1/orders/{oid_b}/invoices", headers=h)

    r = client.get(f"/api/v1/invoices?order_id={oid_a}")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["order_id"] == oid_a


def test_get_invoice_detail_includes_lines_and_total(client: TestClient) -> None:
    h = _login(client)
    oid = _order_with_lines(client, h)
    invoice_id = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"]

    r = client.get(f"/api/v1/invoices/{invoice_id}")
    assert r.status_code == 200
    assert r.json()["draft_total"] == 150.0
    assert len(r.json()["lines"]) == 2


# --- tax_event_date (docs/ACCOUNTANT_REVIEW.md §2): read-only exposure ------
# of a prerequisite field for the future Issue slice. No code anywhere in
# this module ever sets it — every assertion below either checks it is NULL
# through the real create/patch flow, or sets it directly at the DB layer
# (the only way a value can exist today) and checks the API serializes it
# correctly and independently of issued_at.


def test_new_draft_has_null_tax_event_date(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)

    body = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()
    assert body["tax_event_date"] is None


def test_get_invoice_detail_exposes_null_tax_event_date_for_a_draft(
    client: TestClient,
) -> None:
    h = _login(client)
    oid = _order(client, h)
    invoice_id = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"]

    r = client.get(f"/api/v1/invoices/{invoice_id}", headers=h)
    assert r.status_code == 200
    assert r.json()["tax_event_date"] is None


def test_tax_event_date_serializes_as_iso_date_when_set_directly(client: TestClient) -> None:
    """No code in this slice ever writes tax_event_date — that is the future
    Issue workflow's job. Setting it directly at the DB layer is the only
    way to prove the *serialization* shape (exact YYYY-MM-DD) is correct in
    the meantime."""
    import datetime as dt

    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.commercial.models import Invoice

    h = _login(client)
    oid = _order(client, h)
    invoice_id = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"]

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    for db in open_session(url):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        invoice = db.get(Invoice, invoice_id)
        assert invoice is not None
        invoice.tax_event_date = dt.date(2026, 3, 15)
        db.commit()

    r = client.get(f"/api/v1/invoices/{invoice_id}", headers=h)
    assert r.status_code == 200
    assert r.json()["tax_event_date"] == "2026-03-15"


def test_issued_at_and_tax_event_date_are_independent(client: TestClient) -> None:
    """Setting one at the DB layer must never imply or auto-populate the
    other — they are unrelated columns with no synchronization between
    them, matching docs/01: issue timestamp vs. taxable-event calendar
    date are legally distinct concepts."""
    import datetime as dt

    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.commercial.models import Invoice

    h = _login(client)
    oid = _order(client, h)
    invoice_id = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"]

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    for db in open_session(url):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        invoice = db.get(Invoice, invoice_id)
        assert invoice is not None
        invoice.tax_event_date = dt.date(2026, 5, 1)
        db.commit()
        db.refresh(invoice)
        # issued_at was never touched — setting tax_event_date alone must
        # not implicitly populate it.
        assert invoice.issued_at is None
        assert invoice.tax_event_date == dt.date(2026, 5, 1)


def test_draft_creation_never_infers_tax_event_date(client: TestClient) -> None:
    """Explicit regression against every plausible inference source named in
    the task: order creation date, order delivery date, "today", or draft
    creation timestamp — none of them may leak into tax_event_date."""
    h = _login(client)
    oid = _order_with_lines(client, h)

    body = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()
    assert body["tax_event_date"] is None


def test_replace_lines_does_not_change_tax_event_date(client: TestClient) -> None:
    """A directly-set tax_event_date (simulating a value a future Issue
    workflow might have set) must survive an unrelated draft line-replace
    call untouched — replace_lines only ever touches invoice_lines and
    row_version."""
    import datetime as dt

    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.commercial.models import Invoice

    h = _login(client)
    oid = _order_with_lines(client, h)
    invoice_id = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"]

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    for db in open_session(url):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        invoice = db.get(Invoice, invoice_id)
        assert invoice is not None
        invoice.tax_event_date = dt.date(2026, 2, 1)
        db.commit()

    r = client.patch(f"/api/v1/invoices/{invoice_id}", headers=h, json={
        "lines": [{"description": "Ръчен ред", "qty": 1, "unit_price": "10.00",
                  "source": "manual"}],
    })
    assert r.status_code == 200
    assert r.json()["tax_event_date"] == "2026-02-01"


def test_get_invoice_nonexistent_returns_404(client: TestClient) -> None:
    _login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/api/v1/invoices/{fake_id}")
    assert r.status_code == 404
    assert r.json()["detail"]["message_key"] == "errors.invoices.not_found"


def test_patch_replaces_lines_and_bumps_row_version(client: TestClient) -> None:
    h = _login(client)
    oid = _order_with_lines(client, h)
    draft = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()
    assert draft["row_version"] == 1

    r = client.patch(f"/api/v1/invoices/{draft['id']}", headers=h, json={
        "lines": [
            {"description": "Ръчен ред", "qty": 2, "unit_price": "10.00", "source": "manual"},
            {"description": "Отстъпка", "qty": 1, "unit_price": "5.00", "source": "adjustment"},
        ],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["row_version"] == 2
    assert body["draft_total"] == 25.0
    assert {line["source"] for line in body["lines"]} == {"manual", "adjustment"}


def test_patch_on_nonexistent_invoice_returns_404(client: TestClient) -> None:
    h = _login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.patch(f"/api/v1/invoices/{fake_id}", headers=h, json={"lines": []})
    assert r.status_code == 404


def test_replace_lines_rejected_on_non_draft_invoice(client: TestClient) -> None:
    """API-unreachable state today (no issue endpoint exists yet): the order/
    draft are created through the real API like every other test here; only
    flipping status to "issued" — simulating the not-yet-built issue
    endpoint — drops to the DB directly, to prove replace_lines' guard
    exists for when issue lands."""
    import uuid as uuid_mod

    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import TenantContext, bind_tenant_scope, open_session
    from serviceflow.commercial import service as commercial_service

    h = _login(client)
    oid = _order(client, h)
    invoice_id = client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"]

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    for db in open_session(url):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        ctx = TenantContext(company_id=owner.company_id, user_id=owner.id, is_owner=True)

        invoice = commercial_service.get(db, ctx, uuid_mod.UUID(invoice_id))
        assert invoice is not None
        invoice.status = "issued"
        db.commit()

        with pytest.raises(commercial_service.InvoiceError) as exc_info:
            commercial_service.replace_lines(db, ctx, invoice, [])
        assert exc_info.value.message_key == "errors.invoices.not_draft"


def test_cross_tenant_order_cannot_receive_invoice_draft(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid = _order(client, h_a)
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    r = client.post(f"/api/v1/orders/{oid}/invoices", headers=h_b)
    assert r.status_code == 404


def test_cross_tenant_invoice_detail_is_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid = _order(client, h_a)
    invoice_id = client.post(f"/api/v1/orders/{oid}/invoices", headers=h_a).json()["id"]
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    assert client.get(f"/api/v1/invoices/{invoice_id}").status_code == 404
    assert client.get("/api/v1/invoices?status=draft").json() == []


def test_rls_blocks_even_unscoped_invoice_queries(client: TestClient) -> None:
    """ADR-016 layer 3: a raw query that FORGETS scoped() still cannot cross
    tenants (mirrors test_payments.py's equivalent)."""
    from sqlalchemy import select, text

    from business_os.shared_kernel.db import open_session
    from serviceflow.commercial.models import Invoice

    h = _login(client, "Сервиз А", "a@a.bg")
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/invoices", headers=h)

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    for db in open_session(url):
        assert db.scalars(select(Invoice)).all() == []
        db.execute(text(
            "SELECT set_config('app.company_id',"
            " '00000000-0000-0000-0000-000000000000', false)"
        ))
        assert db.scalars(select(Invoice)).all() == []
