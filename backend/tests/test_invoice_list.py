"""Central invoice list (GET /invoices, docs/01 §Invoice's central "Фактури"
workspace): InvoiceListItemOut's batch enrichment (order_number/customer_name/
total), query-level pagination, and the dual customer_name/total sourcing
rule — frozen Invoice.buyer/gross once issued, live Customer/draft-line-sum
while still a draft. See commercial/router.py's module docstring for the
exact contract this exercises."""

import os

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


def _order(client: TestClient, h: dict[str, str], *, customer_name: str = "Иван",
          is_company: bool = False, vat_registered: bool | None = None,
          vat_number: str | None = None) -> str:
    payload: dict[str, object] = {"name": customer_name, "phone": "0888111222"}
    if is_company:
        payload["is_company"] = True
        payload["vat_registered"] = vat_registered
        payload["company_requisites"] = {
            "address": "гр. Пловдив", "eik": VALID_EIK, "vat_number": vat_number,
        }
    cid = client.post("/api/v1/customers", headers=h, json=payload).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone", "field_values": {"brand": "Apple"},
    }).json()["id"]
    return str(client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Не се включва",
    }).json()["id"])


def _order_for_existing_customer(client: TestClient, h: dict[str, str], cid: str) -> str:
    """A second (or third...) order for a customer created by `_order()` —
    `_order()` itself always creates a brand-new customer row, even given
    the same name/phone, so this is the only way to get two orders that
    genuinely share one customer_id."""
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone", "field_values": {"brand": "Apple"},
    }).json()["id"]
    return str(client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Втора поръчка",
    }).json()["id"])


def _order_number(client: TestClient, h: dict[str, str], oid: str) -> str:
    return str(client.get(f"/api/v1/orders/{oid}", headers=h).json()["number"])


def _customer_id_for_order(client: TestClient, h: dict[str, str], oid: str) -> str:
    return str(client.get(f"/api/v1/orders/{oid}", headers=h).json()["customer_id"])


def _order_with_lines(client: TestClient, h: dict[str, str], *,
                      customer_name: str = "Иван", **kwargs: object) -> str:
    oid = _order(client, h, customer_name=customer_name, **kwargs)  # type: ignore[arg-type]
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"name": "Дисплей", "qty": 1, "unit_cost": "60", "unit_price": "100"})
    client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
               json={"description": "Смяна на дисплей", "qty": 1, "unit_price": "50"})
    return oid


def _draft(client: TestClient, h: dict[str, str], oid: str) -> str:
    return str(client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"])


def _issue(client: TestClient, h: dict[str, str], invoice_id: str,
          tax_event_date: str = TAX_EVENT_DATE) -> object:
    return client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=h,
                       json={"tax_event_date": tax_event_date})


def _issued_invoice(client: TestClient, h: dict[str, str], *,
                    customer_name: str = "Иван", **kwargs: object) -> tuple[str, str]:
    """Full flow: seller ready, order + part/labor lines, draft, issue.
    Returns (invoice_id, order_id)."""
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name=customer_name, **kwargs)  # type: ignore[arg-type]
    invoice_id = _draft(client, h, oid)
    r = _issue(client, h, invoice_id)
    assert r.status_code == 200, r.text
    return invoice_id, oid


def _row(body: list[dict[str, object]], invoice_id: str) -> dict[str, object]:
    match = [row for row in body if row["id"] == invoice_id]
    assert len(match) == 1, f"{invoice_id} not found in {body}"
    return match[0]


# --- basic shape / filtering / ordering -------------------------------------

def test_empty_list_returns_empty_array(client: TestClient) -> None:
    _login(client)
    r = client.get("/api/v1/invoices")
    assert r.status_code == 200
    assert r.json() == []


def test_tenant_isolation_excludes_other_company_invoices(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid = _order(client, h_a)
    _draft(client, h_a, oid)
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    assert client.get("/api/v1/invoices").json() == []


def test_newest_first_ordering(client: TestClient) -> None:
    h = _login(client)
    oid1 = _order(client, h)
    first = _draft(client, h, oid1)
    oid2 = _order(client, h)
    second = _draft(client, h, oid2)

    body = client.get("/api/v1/invoices").json()
    ids = [row["id"] for row in body]
    assert ids.index(second) < ids.index(first)


def test_status_draft_filter(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    _draft(client, h, oid)

    body = client.get("/api/v1/invoices?status=draft").json()
    assert len(body) == 1
    assert body[0]["status"] == "draft"


def test_status_issued_filter(client: TestClient) -> None:
    h = _login(client)
    invoice_id, _ = _issued_invoice(client, h)

    body = client.get("/api/v1/invoices?status=issued").json()
    assert [row["id"] for row in body] == [invoice_id]
    assert body[0]["status"] == "issued"


def test_order_id_filter_still_works(client: TestClient) -> None:
    h = _login(client)
    oid_a = _order(client, h)
    oid_b = _order(client, h)
    _draft(client, h, oid_a)
    _draft(client, h, oid_b)

    body = client.get(f"/api/v1/invoices?order_id={oid_a}").json()
    assert len(body) == 1
    assert body[0]["order_id"] == oid_a


# --- customer_id filter (Issue 39) --------------------------------------------

def test_customer_id_filter(client: TestClient) -> None:
    h = _login(client)
    oid_a = _order(client, h, customer_name="Клиент А")
    oid_b = _order(client, h, customer_name="Клиент Б")
    invoice_a = _draft(client, h, oid_a)
    _draft(client, h, oid_b)
    cid_a = _customer_id_for_order(client, h, oid_a)

    body = client.get(f"/api/v1/invoices?customer_id={cid_a}").json()
    assert [row["id"] for row in body] == [invoice_a]


def test_customer_id_filter_covers_all_of_that_customers_orders(client: TestClient) -> None:
    """One customer, two separate orders/invoices — both must come back, not
    just the first (an accidental single order_id match would miss this)."""
    h = _login(client)
    oid1 = _order(client, h, customer_name="Редовен клиент")
    cid = _customer_id_for_order(client, h, oid1)
    oid2 = _order_for_existing_customer(client, h, cid)
    invoice1 = _draft(client, h, oid1)
    invoice2 = _draft(client, h, oid2)

    body = client.get(f"/api/v1/invoices?customer_id={cid}").json()
    assert {row["id"] for row in body} == {invoice1, invoice2}


def test_customer_id_filter_composes_with_status(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="Клиент А")
    draft_id = _draft(client, h, oid)
    cid = _customer_id_for_order(client, h, oid)
    _issue(client, h, draft_id)

    other_oid = _order(client, h, customer_name="Клиент Б")
    _draft(client, h, other_oid)

    body = client.get(f"/api/v1/invoices?customer_id={cid}&status=issued").json()
    assert [row["id"] for row in body] == [draft_id]


def test_customer_id_filter_composes_with_pagination(client: TestClient) -> None:
    h = _login(client)
    oid1 = _order(client, h, customer_name="Много поръчки")
    cid = _customer_id_for_order(client, h, oid1)
    invoice_ids = [_draft(client, h, oid1)]
    for _ in range(4):
        oid = _order_for_existing_customer(client, h, cid)
        invoice_ids.append(_draft(client, h, oid))
    newest_first = list(reversed(invoice_ids))

    page1 = client.get(f"/api/v1/invoices?customer_id={cid}&limit=2&offset=0").json()
    page2 = client.get(f"/api/v1/invoices?customer_id={cid}&limit=2&offset=2").json()
    assert [row["id"] for row in page1] == newest_first[0:2]
    assert [row["id"] for row in page2] == newest_first[2:4]


def test_customer_id_filter_is_tenant_isolated(client: TestClient) -> None:
    """A customer_id from another tenant must never leak that tenant's
    invoices — get_order_ids_for_customer resolves through the same scoped()
    chokepoint as every other tenant query, this proves it end to end."""
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid_a = _order(client, h_a, customer_name="Клиент А")
    _draft(client, h_a, oid_a)
    cid_a = _customer_id_for_order(client, h_a, oid_a)
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    body = client.get(f"/api/v1/invoices?customer_id={cid_a}").json()
    assert body == []


# --- pagination --------------------------------------------------------------

def test_default_limit_is_50(client: TestClient) -> None:
    h = _login(client)
    for _ in range(55):
        _draft(client, h, _order(client, h))

    body = client.get("/api/v1/invoices").json()
    assert len(body) == 50


def test_custom_limit_applied(client: TestClient) -> None:
    h = _login(client)
    for _ in range(5):
        _draft(client, h, _order(client, h))

    body = client.get("/api/v1/invoices?limit=2").json()
    assert len(body) == 2


def test_offset_applied(client: TestClient) -> None:
    h = _login(client)
    ids = [_draft(client, h, _order(client, h)) for _ in range(5)]
    newest_first = list(reversed(ids))

    page1 = client.get("/api/v1/invoices?limit=2&offset=0").json()
    page2 = client.get("/api/v1/invoices?limit=2&offset=2").json()
    assert [row["id"] for row in page1] == newest_first[0:2]
    assert [row["id"] for row in page2] == newest_first[2:4]


def test_invalid_limit_rejected(client: TestClient) -> None:
    """FastAPI Query() validation failures render through this app's own
    RequestValidationError handler (serviceflow/main.py) — 400, not FastAPI's
    stock 422, matching every other endpoint's error envelope."""
    _login(client)
    for bad in ("0", "-1", "201"):
        r = client.get(f"/api/v1/invoices?limit={bad}")
        assert r.status_code == 400
        assert r.json()["message_key"] == "errors.validation"


def test_invalid_offset_rejected(client: TestClient) -> None:
    _login(client)
    r = client.get("/api/v1/invoices?offset=-1")
    assert r.status_code == 400
    assert r.json()["message_key"] == "errors.validation"


# --- number semantics ---------------------------------------------------------

def test_draft_number_is_null(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    _draft(client, h, oid)

    body = client.get("/api/v1/invoices").json()
    assert body[0]["number"] is None


def test_issued_number_preserved_as_stored_integer(client: TestClient) -> None:
    h = _login(client)
    invoice_id, _ = _issued_invoice(client, h)

    body = client.get("/api/v1/invoices?status=issued").json()
    row = _row(body, invoice_id)
    assert row["number"] == 1
    assert isinstance(row["number"], int)


# --- customer_name dual sourcing ---------------------------------------------

def test_draft_customer_name_from_live_customer(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h, customer_name="Драфт Клиент")
    _draft(client, h, oid)

    body = client.get("/api/v1/invoices?status=draft").json()
    assert body[0]["customer_name"] == "Драфт Клиент"


def test_issued_customer_name_from_frozen_buyer_snapshot(client: TestClient) -> None:
    h = _login(client)
    invoice_id, _ = _issued_invoice(client, h, customer_name="Издаден Клиент")

    body = client.get("/api/v1/invoices?status=issued").json()
    assert _row(body, invoice_id)["customer_name"] == "Издаден Клиент"


def test_edit_customer_after_issue_list_row_still_shows_snapshot_name(
    client: TestClient,
) -> None:
    h = _login(client)
    invoice_id, oid = _issued_invoice(client, h, customer_name="Оригинално Име")
    cid = _customer_id_for_order(client, h, oid)

    r = client.patch(f"/api/v1/customers/{cid}", headers=h, json={"name": "Ново Име"})
    assert r.status_code == 200, r.text

    body = client.get("/api/v1/invoices?status=issued").json()
    row = _row(body, invoice_id)
    assert row["customer_name"] == "Оригинално Име"
    assert row["customer_name"] != "Ново Име"


def test_issued_customer_name_from_frozen_buyer_snapshot_for_company_buyer(
    client: TestClient,
) -> None:
    h = _login(client)
    invoice_id, _ = _issued_invoice(client, h, customer_name="Издадена Фирма ЕООД",
                                    is_company=True, vat_registered=False)

    body = client.get("/api/v1/invoices?status=issued").json()
    assert _row(body, invoice_id)["customer_name"] == "Издадена Фирма ЕООД"


def test_edit_company_customer_after_issue_list_row_still_shows_snapshot_name(
    client: TestClient,
) -> None:
    h = _login(client)
    invoice_id, oid = _issued_invoice(client, h, customer_name="Оригинална Фирма ЕООД",
                                      is_company=True, vat_registered=True,
                                      vat_number="BG130489869")
    cid = _customer_id_for_order(client, h, oid)

    r = client.patch(f"/api/v1/customers/{cid}", headers=h, json={"name": "Нова Фирма ЕООД"})
    assert r.status_code == 200, r.text

    body = client.get("/api/v1/invoices?status=issued").json()
    row = _row(body, invoice_id)
    assert row["customer_name"] == "Оригинална Фирма ЕООД"
    assert row["customer_name"] != "Нова Фирма ЕООД"


def test_edit_customer_on_draft_list_row_reflects_live_name(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h, customer_name="Старо Име")
    invoice_id = _draft(client, h, oid)
    cid = _customer_id_for_order(client, h, oid)

    r = client.patch(f"/api/v1/customers/{cid}", headers=h, json={"name": "Ново Име"})
    assert r.status_code == 200, r.text

    body = client.get("/api/v1/invoices?status=draft").json()
    row = _row(body, invoice_id)
    assert row["customer_name"] == "Ново Име"


# --- order_number --------------------------------------------------------------

def test_order_number_populated_correctly(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    invoice_id = _draft(client, h, oid)
    expected = _order_number(client, h, oid)

    body = client.get("/api/v1/invoices").json()
    assert _row(body, invoice_id)["order_number"] == expected


# --- total semantics -----------------------------------------------------------

def test_draft_total_semantics(client: TestClient) -> None:
    h = _login(client)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    body = client.get("/api/v1/invoices?status=draft").json()
    assert _row(body, invoice_id)["total"] == 150.0


def test_issued_total_equals_frozen_gross(client: TestClient) -> None:
    h = _login(client)
    invoice_id, _ = _issued_invoice(client, h)

    detail = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()
    body = client.get("/api/v1/invoices?status=issued").json()
    row = _row(body, invoice_id)
    assert row["total"] == detail["gross"]
    assert row["total"] == 150.0


# --- cross-tenant enrichment / N+1 --------------------------------------------

def test_no_cross_tenant_enrichment(client: TestClient) -> None:
    """Each tenant's list rows must resolve order_number/customer_name from
    their OWN order/customer only — proven with data, not just presence/
    absence, so a scoping bug in the batch-enrichment path (as opposed to the
    already-covered list-membership isolation) would be caught too."""
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid_a = _order(client, h_a, customer_name="Клиент А")
    invoice_a = _draft(client, h_a, oid_a)
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    oid_b = _order(client, h_b, customer_name="Клиент Б")
    invoice_b = _draft(client, h_b, oid_b)
    number_b = _order_number(client, h_b, oid_b)

    body_b = client.get("/api/v1/invoices", headers=h_b).json()
    assert [row["id"] for row in body_b] == [invoice_b]
    row = _row(body_b, invoice_b)
    # Order numbering is a fresh per-company sequence (both tenants' first
    # order is legitimately "2026-00001") — the real leakage signal is B's
    # row resolving B's OWN customer/order data, not merely a different
    # order_number string.
    assert row["customer_name"] == "Клиент Б"
    assert row["order_number"] == number_b
    assert invoice_a  # sanity: tenant A's invoice exists but is not in body_b


def test_no_n_plus_1_behavior_for_multi_row_page(client: TestClient) -> None:
    """Query-count guard, not an exact-count assertion (robust against
    framework/session overhead, per this slice's own instructions): the
    number of SELECTs issued while listing invoices must not grow with the
    number of rows returned — proves the batch-enrichment path (order
    summaries, customer summaries, draft totals) stays at O(1) queries per
    page, not O(n)."""
    from sqlalchemy import event

    from business_os.shared_kernel.db import get_engine

    h = _login(client)
    _ready_seller(client, h)
    for i in range(2):
        oid = _order_with_lines(client, h, customer_name=f"Клиент {i}")
        invoice_id = _draft(client, h, oid)
        if i == 0:
            _issue(client, h, invoice_id)
    # One draft, one issued among the first 2 — exercise both enrichment paths.

    engine = get_engine(os.environ["SERVICEFLOW_DATABASE_URL"])

    def _count_selects(fn: object) -> int:
        count = 0

        def _listener(conn: object, cursor: object, statement: str, *_: object) -> None:
            nonlocal count
            if statement.strip().upper().startswith("SELECT"):
                count += 1

        event.listen(engine, "before_cursor_execute", _listener)
        try:
            fn()  # type: ignore[operator]
        finally:
            event.remove(engine, "before_cursor_execute", _listener)
        return count

    small_page = _count_selects(lambda: client.get("/api/v1/invoices?limit=2", headers=h))

    for i in range(2, 10):
        oid = _order_with_lines(client, h, customer_name=f"Клиент {i}")
        _draft(client, h, oid)
    # 10 rows total now (1 issued + 9 draft) — a genuinely larger page.

    large_page = _count_selects(lambda: client.get("/api/v1/invoices?limit=10", headers=h))

    assert large_page <= small_page + 2, (
        f"SELECT count grew with row count ({small_page} -> {large_page}) — "
        "looks like a per-row (N+1) query was introduced"
    )
