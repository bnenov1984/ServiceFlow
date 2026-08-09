"""Invoice Issue (docs/ACCOUNTANT_REVIEW.md 'RepairFlow Invoice V1 Freeze'
§5 / §4 B1 / §6): POST /invoices/{id}/issue. The seller may be non-VAT-
registered or VAT-registered at the single standard 20% rate; the buyer may
be an individual or a domestic company (VAT-registered or not) — everything
else (mixed VAT rates, incomplete/unknown-VAT-status company buyer) must
fail deterministically before number allocation. See commercial/service.py's
`issue()` for the exact transaction algorithm this exercises."""

import os
import threading
import uuid as uuid_mod

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
    """PATCHes Company.requisites to the minimum Phase-A-supported seller
    shape (address + eik, vat_registered left at its False default)."""
    resp = client.patch("/api/v1/company/requisites", headers=h,
                        json={"address": "гр. София, ул. Примерна 1", "eik": eik})
    assert resp.status_code == 200, resp.text


def _ready_vat_seller(client: TestClient, h: dict[str, str], eik: str = VALID_EIK) -> None:
    """Same as _ready_seller, plus vat_registered=True."""
    _ready_seller(client, h, eik)
    resp = client.patch("/api/v1/company/requisites", headers=h, json={"vat_registered": True})
    assert resp.status_code == 200, resp.text


def _order(client: TestClient, h: dict[str, str], *,
          customer_name: str = "Иван", is_company: bool = False,
          vat_registered: bool | None = None,
          company_address: str | None = "гр. Пловдив",
          company_eik: str | None = VALID_EIK,
          vat_number: str | None = None) -> str:
    payload: dict[str, object] = {"name": customer_name, "phone": "0888111222"}
    if is_company:
        payload["is_company"] = True
        payload["vat_registered"] = vat_registered
        payload["company_requisites"] = {
            "address": company_address, "eik": company_eik, "vat_number": vat_number,
        }
    resp = client.post("/api/v1/customers", headers=h, json=payload)
    assert resp.status_code == 201, resp.text
    cid = resp.json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone", "field_values": {"brand": "Apple"},
    }).json()["id"]
    return str(client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Не се включва",
    }).json()["id"])


def _order_with_lines(client: TestClient, h: dict[str, str], **kwargs: object) -> str:
    oid = _order(client, h, **kwargs)  # type: ignore[arg-type]
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"name": "Дисплей", "qty": 1, "unit_cost": "60", "unit_price": "100"})
    client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
               json={"description": "Смяна на дисплей", "qty": 1, "unit_price": "50"})
    return oid


def _draft(client: TestClient, h: dict[str, str], oid: str) -> str:
    return str(client.post(f"/api/v1/orders/{oid}/invoices", headers=h).json()["id"])


def _issue(client: TestClient, h: dict[str, str], invoice_id: str,
          tax_event_date: str = TAX_EVENT_DATE) -> "object":
    return client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=h,
                       json={"tax_event_date": tax_event_date})


def _new_session(url: str) -> Session:
    """A standalone session the caller owns and closes explicitly — same
    shape as test_document_sequences.py's helper, needed to hold a
    transaction open across a thread-blocking window."""
    from sqlalchemy.orm import sessionmaker

    from business_os.shared_kernel.db import get_engine

    return sessionmaker(bind=get_engine(url), expire_on_commit=False, class_=Session)()


def _sequence_current(company_id: uuid_mod.UUID) -> int | None:
    """None if no invoice sequence row exists yet for this company — the
    exact signal "no number has ever been allocated" for this tenant."""
    from sqlalchemy import select

    from business_os.shared_kernel.db import open_session
    from serviceflow.service_orders.models import DocumentSequence

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        row = db.scalar(select(DocumentSequence).where(
            DocumentSequence.company_id == company_id, DocumentSequence.kind == "invoice",
        ))
        return row.current if row is not None else None
    raise AssertionError("unreachable")


def _owner_company_id(email: str = "a@a.bg") -> uuid_mod.UUID:
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == email))
        assert owner is not None
        return owner.company_id
    raise AssertionError("unreachable")


def _timeline_events(order_id: str, event_type: str = "invoice_issued",
                     owner_email: str = "a@a.bg") -> list[object]:
    """RLS-protected — bind_tenant_scope is required or every row is
    silently invisible (fail-closed), not an empty-but-real result."""
    from sqlalchemy import select

    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.timeline.models import TimelineEvent

    company_id = _owner_company_id(owner_email)
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        bind_tenant_scope(db, company_id)
        return list(db.scalars(select(TimelineEvent).where(
            TimelineEvent.order_id == uuid_mod.UUID(order_id),
            TimelineEvent.event_type == event_type,
        )))
    raise AssertionError("unreachable")


def _customer_id_for_order(order_id: str, owner_email: str = "a@a.bg") -> uuid_mod.UUID:
    from sqlalchemy import select

    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.service_orders.models import ServiceOrder

    company_id = _owner_company_id(owner_email)
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        bind_tenant_scope(db, company_id)
        order = db.scalar(select(ServiceOrder).where(ServiceOrder.id == uuid_mod.UUID(order_id)))
        assert order is not None
        return order.customer_id
    raise AssertionError("unreachable")


def _set_company_requisites_directly(customer_id: uuid_mod.UUID, requisites: dict[str, object],
                                     owner_email: str = "a@a.bg") -> None:
    """Bypasses `customers/router.py`'s Pydantic-level EIK/VAT-number format
    validation and `customers/service.py`'s `_validate_vat_identity` — the
    only way to put a Customer row into a state today's UI/API can no longer
    produce (stale/legacy data), which is exactly what Issue's own defensive
    re-validation (mirroring the seller-side EIK re-check) exists to guard
    against."""
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.customers.models import Customer

    company_id = _owner_company_id(owner_email)
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        bind_tenant_scope(db, company_id)
        customer = db.scalar(select(Customer).where(Customer.id == customer_id))
        assert customer is not None
        customer.company_requisites = {**(customer.company_requisites or {}), **requisites}
        flag_modified(customer, "company_requisites")
        db.commit()


# --- Happy path --------------------------------------------------------


def test_non_vat_seller_and_individual_buyer_issues_successfully(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="Иван Петров")
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["status"] == "issued"
    assert body["number"] == 1
    assert body["tax_event_date"] == TAX_EVENT_DATE
    assert body["issued_at"] is not None
    assert body["seller"] == {
        "name": "Сервиз А", "address": "гр. София, ул. Примерна 1",
        "eik": VALID_EIK, "vat_registered": False,
    }
    assert body["buyer"] == {"name": "Иван Петров"}
    assert body["vat_mode"] == "not_registered"
    assert body["net"] == 150.0
    assert body["vat"] == 0.0
    assert body["gross"] == 150.0
    assert body["draft_total"] == 150.0
    assert body["row_version"] == 2

    events = _timeline_events(oid)
    assert len(events) == 1
    assert events[0].data == {"invoice_id": invoice_id, "invoice_number": "0000000001"}


def test_issued_invoice_is_reflected_on_get(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    resp = client.get(f"/api/v1/invoices/{invoice_id}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "issued"
    assert resp.json()["number"] == 1


def test_non_vat_company_buyer_issues_successfully(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="Пример ЕООД", is_company=True,
                            vat_registered=False, company_address="гр. Пловдив",
                            company_eik=VALID_EIK)
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "issued"
    assert body["buyer"] == {
        "name": "Пример ЕООД", "address": "гр. Пловдив", "eik": VALID_EIK,
        "vat_registered": False,
    }
    # Seller stays non-VAT-registered regardless of buyer type.
    assert body["vat_mode"] == "not_registered"
    assert body["net"] == 150.0
    assert body["vat"] == 0.0
    assert body["gross"] == 150.0

    detail = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()
    assert detail["buyer"] == body["buyer"]


def test_non_vat_company_buyer_stale_vat_number_not_copied(client: TestClient) -> None:
    """A company customer may have a leftover vat_number in company_requisites
    from before vat_registered was set back to False (docs' own "choosing
    'Не' clears any draft VAT number from the save payload" UI behavior
    notwithstanding — this proves the backend never trusts it either)."""
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="Пример ЕООД", is_company=True,
                            vat_registered=False)
    cid = _customer_id_for_order(oid)
    _set_company_requisites_directly(cid, {"vat_number": "BG130489869"})
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["buyer"] == {
        "name": "Пример ЕООД", "address": "гр. Пловдив", "eik": VALID_EIK,
        "vat_registered": False,
    }
    assert "vat_number" not in resp.json()["buyer"]


def test_vat_registered_company_buyer_issues_successfully(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="ДДС ЕООД", is_company=True,
                            vat_registered=True, company_address="гр. Варна",
                            company_eik=VALID_EIK, vat_number="BG130489869")
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["buyer"] == {
        "name": "ДДС ЕООД", "address": "гр. Варна", "eik": VALID_EIK,
        "vat_registered": True, "vat_number": "BG130489869",
    }
    # The buyer being VAT-registered never makes the (non-VAT) seller charge VAT.
    assert body["vat_mode"] == "not_registered"
    assert body["vat"] == 0.0
    assert body["gross"] == body["net"]

    detail = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()
    assert detail["buyer"] == body["buyer"]


def test_vat_registered_company_buyer_vat_number_normalized(client: TestClient) -> None:
    """The stored value only has incidental whitespace to strip (as if it
    predates today's Customer-create-time normalization) — Issue must
    still normalize it fresh rather than trust the stored bytes verbatim,
    same defensive posture as the seller-side EIK re-check."""
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="ДДС ЕООД", is_company=True,
                            vat_registered=True, vat_number="BG130489869")
    cid = _customer_id_for_order(oid)
    _set_company_requisites_directly(cid, {"vat_number": " BG130489869 "})
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["buyer"]["vat_number"] == "BG130489869"


def test_vat_registered_seller_issues_successfully_with_exact_calculation(
    client: TestClient,
) -> None:
    """Frozen V1 rule (docs/ACCOUNTANT_REVIEW.md §6): net = Σ(qty×unit_price),
    one VAT calculation on the invoice total (never per-line), vat_mode
    "registered", seller snapshot carries the derived "BG"+ЕИК VAT number,
    every line's vat_rate frozen to the single standard 20.00 rate."""
    h = _login(client)
    _ready_vat_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="Иван Петров")
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["vat_mode"] == "registered"
    assert body["seller"] == {
        "name": "Сервиз А", "address": "гр. София, ул. Примерна 1",
        "eik": VALID_EIK, "vat_registered": True, "vat_number": f"BG{VALID_EIK}",
    }
    assert body["net"] == 150.0
    assert body["vat"] == 30.0  # 150 * 0.20, no rounding ambiguity
    assert body["gross"] == 180.0
    for line in body["lines"]:
        assert line["vat_rate"] == 20.0

    detail = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()
    assert detail["seller"] == body["seller"]
    assert detail["vat"] == 30.0


def test_vat_registered_seller_vat_amount_rounds_half_up(client: TestClient) -> None:
    """10.03 * 0.20 = 2.006 -> ROUND_HALF_UP to 2 decimal places = 2.01,
    proving the exact frozen formula
    (net * Decimal("0.20")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    is what actually runs, not e.g. plain float rounding or truncation."""
    h = _login(client)
    _ready_vat_seller(client, h)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"name": "Част", "qty": 1, "unit_cost": "5", "unit_price": "10.03"})
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["net"] == 10.03
    assert body["vat"] == 2.01
    assert body["gross"] == 12.04


def test_vat_registered_seller_calculation_unaffected_by_vat_registered_buyer(
    client: TestClient,
) -> None:
    """A VAT-registered buyer never changes the seller's own calculation —
    same 20%-of-net result as the individual-buyer happy path above."""
    h = _login(client)
    _ready_vat_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="ДДС Клиент ЕООД", is_company=True,
                            vat_registered=True, vat_number="BG130489869")
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["vat_mode"] == "registered"
    assert body["net"] == 150.0
    assert body["vat"] == 30.0
    assert body["gross"] == 180.0
    assert body["buyer"]["vat_registered"] is True  # buyer is VAT-registered too


# --- Validation ----------------------------------------------------------


def test_non_draft_invoice_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)
    assert _issue(client, h, invoice_id).status_code == 200

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.not_draft"


def test_empty_invoice_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order(client, h)  # no part/labor lines
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.empty"


def test_seller_missing_address_rejected(client: TestClient) -> None:
    h = _login(client)
    client.patch("/api/v1/company/requisites", headers=h, json={"eik": VALID_EIK})
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.seller_incomplete"


def test_seller_missing_eik_rejected(client: TestClient) -> None:
    h = _login(client)
    client.patch("/api/v1/company/requisites", headers=h,
                json={"address": "гр. София, ул. Примерна 1"})
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.seller_incomplete"


def test_vat_registered_seller_mixed_rate_line_rejected(client: TestClient) -> None:
    """Only the single standard rate is supported: a line with a rate that
    is neither NULL nor exactly 20.00 (never reachable through the normal
    UI, which exposes no vat_rate input) is rejected as a mixed/unsupported
    VAT state — same error and same reasoning that already rejected any
    non-NULL rate for a non-VAT-registered seller."""
    h = _login(client)
    _ready_vat_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)
    resp = client.patch(f"/api/v1/invoices/{invoice_id}", headers=h, json={
        "lines": [{"description": "Ред с друга ставка", "qty": 1, "unit_price": "10.00",
                  "vat_rate": "9", "source": "manual"}],
    })
    assert resp.status_code == 200

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.vat_state_invalid"


def test_company_buyer_vat_status_unknown_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, is_company=True)  # vat_registered left at its NULL default
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.buyer_vat_status_unknown"


def test_company_buyer_missing_address_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, is_company=True, vat_registered=False,
                            company_address=None)
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.buyer_incomplete"


def test_company_buyer_missing_eik_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, is_company=True, vat_registered=False, company_eik=None)
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.buyer_incomplete"


def test_company_buyer_invalid_eik_rejected(client: TestClient) -> None:
    """Stale/legacy data only — today's Customer create/update path already
    rejects a malformed EIK, so this simulates data that predates that
    validation (mirrors the seller-side EIK re-check's own rationale)."""
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, is_company=True, vat_registered=False)
    cid = _customer_id_for_order(oid)
    _set_company_requisites_directly(cid, {"eik": "123"})
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.buyer_incomplete"


def test_company_buyer_vat_registered_missing_vat_number_rejected(client: TestClient) -> None:
    """Stale/legacy data only — today's Customer path requires a vat_number
    whenever vat_registered=True (customers/service.py's
    `_validate_vat_identity`), so this simulates data from before that rule
    existed, exercising Issue's own independent re-check."""
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, is_company=True, vat_registered=True,
                            vat_number="BG130489869")
    cid = _customer_id_for_order(oid)
    _set_company_requisites_directly(cid, {"vat_number": None})
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.buyer_vat_number_invalid"


def test_company_buyer_vat_registered_invalid_vat_number_format_rejected(
    client: TestClient,
) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, is_company=True, vat_registered=True,
                            vat_number="BG130489869")
    cid = _customer_id_for_order(oid)
    _set_company_requisites_directly(cid, {"vat_number": "FR130489869"})
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.buyer_vat_number_invalid"


def test_non_null_line_vat_rate_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)
    resp = client.patch(f"/api/v1/invoices/{invoice_id}", headers=h, json={
        "lines": [{"description": "Ред с ДДС", "qty": 1, "unit_price": "10.00",
                  "vat_rate": "20", "source": "manual"}],
    })
    assert resp.status_code == 200

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.vat_state_invalid"


def test_missing_tax_event_date_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    resp = client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=h, json={})
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_invalid_tax_event_date_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id, tax_event_date="not-a-date")
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_wrong_tenant_returns_404(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    _ready_seller(client, h_a)
    oid = _order_with_lines(client, h_a)
    invoice_id = _draft(client, h_a, oid)
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    resp = _issue(client, h_b, invoice_id)
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.invoices.not_found"


def test_worker_forbidden(client: TestClient) -> None:
    h_owner = _login(client)
    _ready_seller(client, h_owner)
    oid = _order_with_lines(client, h_owner)
    invoice_id = _draft(client, h_owner, oid)
    client.post("/api/v1/users", headers=h_owner,
               json={"name": "Иво", "email": "ivo@a.bg", "password": "парола-за-иво-123"})
    client.post("/api/v1/auth/logout", headers=h_owner)

    me = client.post("/api/v1/auth/login",
                     json={"email": "ivo@a.bg", "password": "парола-за-иво-123"}).json()
    h_worker = {"X-CSRF-Token": str(me["csrf_token"])}
    resp = _issue(client, h_worker, invoice_id)
    assert resp.status_code == 403
    assert resp.json()["detail"]["message_key"] == "errors.auth.owner_required"


def test_missing_csrf_forbidden(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    resp = client.post(f"/api/v1/invoices/{invoice_id}/issue",
                       json={"tax_event_date": TAX_EVENT_DATE})
    assert resp.status_code == 403
    assert resp.json()["detail"]["message_key"] == "errors.auth.csrf"


def test_suspended_subscription_blocked(client: TestClient) -> None:
    from business_os.identity.models import Company
    from business_os.shared_kernel.db import open_session

    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        from sqlalchemy import select

        from business_os.identity.models import User
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        company = db.get(Company, owner.company_id)
        assert company is not None
        company.subscription_state = "suspended"
        db.commit()

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 402
    assert resp.json()["detail"]["message_key"] == "errors.subscription.mutations_blocked"


# --- Atomicity -------------------------------------------------------------


def test_seller_incomplete_failure_consumes_no_number(client: TestClient) -> None:
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    h = _login(client)  # seller left incomplete (no requisites set)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        assert _sequence_current(owner.company_id) is None

    assert client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()["number"] is None
    assert _timeline_events(oid) == []


def test_company_buyer_vat_status_unknown_failure_consumes_no_number(
    client: TestClient,
) -> None:
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, is_company=True)
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        assert _sequence_current(owner.company_id) is None
    assert _timeline_events(oid) == []


def test_company_buyer_incomplete_failure_consumes_no_number(client: TestClient) -> None:
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, is_company=True, vat_registered=False,
                            company_address=None)
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        assert _sequence_current(owner.company_id) is None
    assert client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()["number"] is None
    assert _timeline_events(oid) == []


def test_company_buyer_vat_number_invalid_failure_consumes_no_number(
    client: TestClient,
) -> None:
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, is_company=True, vat_registered=True,
                            vat_number="BG130489869")
    cid = _customer_id_for_order(oid)
    _set_company_requisites_directly(cid, {"vat_number": None})
    invoice_id = _draft(client, h, oid)

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        assert _sequence_current(owner.company_id) is None
    assert _timeline_events(oid) == []


def test_vat_registered_seller_mixed_rate_failure_consumes_no_number(
    client: TestClient,
) -> None:
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    h = _login(client)
    _ready_vat_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)
    client.patch(f"/api/v1/invoices/{invoice_id}", headers=h, json={
        "lines": [{"description": "Ред с друга ставка", "qty": 1, "unit_price": "10.00",
                  "vat_rate": "9", "source": "manual"}],
    })

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        assert _sequence_current(owner.company_id) is None
    assert _timeline_events(oid) == []


def test_vat_state_failure_consumes_no_number(client: TestClient) -> None:
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)
    client.patch(f"/api/v1/invoices/{invoice_id}", headers=h, json={
        "lines": [{"description": "Ред с ДДС", "qty": 1, "unit_price": "10.00",
                  "vat_rate": "20", "source": "manual"}],
    })

    resp = _issue(client, h, invoice_id)
    assert resp.status_code == 409

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        assert _sequence_current(owner.company_id) is None
    assert _timeline_events(oid) == []


def test_failure_after_number_allocation_rolls_back_sequence_and_invoice(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deterministic injection (not timing): monkeypatch publish() — called
    after every write and after number allocation, immediately before the
    single commit — to raise. The whole transaction (writes + the sequence
    upsert) must roll back together, exactly as if nothing had happened."""
    import datetime as dt

    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import TenantContext, bind_tenant_scope, open_session
    from serviceflow.commercial import service as commercial_service

    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("forced failure after number allocation, before commit")

    monkeypatch.setattr(commercial_service, "publish", _boom)

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_id = None
    for db in open_session(url):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        company_id = owner.company_id
        bind_tenant_scope(db, owner.company_id)
        ctx = TenantContext(company_id=owner.company_id, user_id=owner.id, is_owner=True)
        with pytest.raises(RuntimeError):
            commercial_service.issue(db, ctx, uuid_mod.UUID(invoice_id), dt.date(2026, 3, 1))
        db.rollback()

    assert company_id is not None
    assert _sequence_current(company_id) is None, (
        "sequence increment was not rolled back after a post-allocation failure"
    )

    body = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()
    assert body["status"] == "draft"
    assert body["number"] is None
    assert body["seller"] is None
    assert body["buyer"] is None
    assert body["net"] is None
    assert body["vat"] is None
    assert body["gross"] is None
    assert body["issued_at"] is None
    assert _timeline_events(oid) == []


# --- Concurrency -------------------------------------------------------


def test_concurrent_issue_same_invoice_exactly_one_succeeds(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Thread A is deliberately paused (via a patched publish()) after it
    has locked the row, allocated a number, and written every Issue field —
    but before its commit. Thread B, started while A is still open, must
    genuinely block on the FOR UPDATE lock (proven via thread.is_alive(),
    not timing), then unblock once A commits and see status != draft."""
    import datetime as dt

    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import TenantContext, bind_tenant_scope, open_session
    from serviceflow.commercial import service as commercial_service

    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = uuid_mod.UUID(_draft(client, h, oid))

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    owner_id = None
    company_id = None
    for db in open_session(url):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        owner_id, company_id = owner.id, owner.company_id
    assert owner_id is not None and company_id is not None
    ctx = TenantContext(company_id=company_id, user_id=owner_id, is_owner=True)

    reached_publish = threading.Event()
    release_a = threading.Event()
    real_publish = commercial_service.publish

    def _paused_publish(db: Session, event: object) -> None:
        reached_publish.set()
        assert release_a.wait(timeout=10), "test never released thread A"
        real_publish(db, event)

    monkeypatch.setattr(commercial_service, "publish", _paused_publish)

    result_a: list[object] = []

    def run_a() -> None:
        session_a = _new_session(url)
        bind_tenant_scope(session_a, company_id)
        try:
            invoice = commercial_service.issue(session_a, ctx, invoice_id, dt.date(2026, 3, 1))
            result_a.append(invoice.number)
        except BaseException as exc:  # noqa: BLE001 — captured, asserted below
            result_a.append(exc)
        finally:
            session_a.close()

    thread_a = threading.Thread(target=run_a)
    thread_a.start()
    assert reached_publish.wait(timeout=5), "thread A never reached the pre-commit hold point"

    result_b: list[object] = []

    def run_b() -> None:
        session_b = _new_session(url)
        bind_tenant_scope(session_b, company_id)
        try:
            commercial_service.issue(session_b, ctx, invoice_id, dt.date(2026, 3, 2))
            result_b.append("succeeded")
        except BaseException as exc:  # noqa: BLE001 — captured, asserted below
            result_b.append(exc)
        finally:
            session_b.close()

    thread_b = threading.Thread(target=run_b)
    thread_b.start()
    thread_b.join(timeout=1)
    assert thread_b.is_alive(), "loser did not block on the contested Invoice row lock"

    release_a.set()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)
    assert not thread_a.is_alive()
    assert not thread_b.is_alive()

    assert len(result_a) == 1 and result_a[0] == 1, f"winner did not issue cleanly: {result_a!r}"
    assert len(result_b) == 1
    assert isinstance(result_b[0], commercial_service.InvoiceError)
    assert result_b[0].message_key == "errors.invoices.not_draft"

    assert _sequence_current(company_id) == 1, "exactly one number must have been consumed"
    assert len(_timeline_events(oid)) == 1, "exactly one timeline event must exist"


def test_concurrent_issue_two_invoices_same_company_both_succeed(client: TestClient) -> None:
    """Two different drafts, same company, issued from two real threads at
    (as close to) the same instant via a Barrier — both must succeed with
    distinct sequential numbers and no deadlock, since neither thread ever
    locks the *other's* Invoice row (only its own, then the shared
    document_sequences row, serialized by the already-proven-safe upsert)."""
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import TenantContext, bind_tenant_scope, open_session
    from serviceflow.commercial import service as commercial_service

    h = _login(client)
    _ready_seller(client, h)
    oid_1 = _order_with_lines(client, h)
    oid_2 = _order_with_lines(client, h)
    invoice_1 = uuid_mod.UUID(_draft(client, h, oid_1))
    invoice_2 = uuid_mod.UUID(_draft(client, h, oid_2))

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_id = None
    owner_id = None
    for db in open_session(url):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        owner_id, company_id = owner.id, owner.company_id
    assert owner_id is not None and company_id is not None
    ctx = TenantContext(company_id=company_id, user_id=owner_id, is_owner=True)

    barrier = threading.Barrier(2)
    results: list[object] = [None, None]

    def run(index: int, invoice_id: uuid_mod.UUID, day: int) -> None:
        import datetime as dt

        db = _new_session(url)
        bind_tenant_scope(db, company_id)
        try:
            barrier.wait(timeout=10)
            invoice = commercial_service.issue(db, ctx, invoice_id, dt.date(2026, 3, day))
            results[index] = invoice.number
        except BaseException as exc:  # noqa: BLE001 — captured, asserted below
            results[index] = exc
        finally:
            db.close()

    threads = [
        threading.Thread(target=run, args=(0, invoice_1, 1)),
        threading.Thread(target=run, args=(1, invoice_2, 2)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    for i, result in enumerate(results):
        assert not isinstance(result, BaseException), f"thread {i} failed: {result!r}"
    assert set(results) == {1, 2}
    assert len(_timeline_events(oid_1)) == 1
    assert len(_timeline_events(oid_2)) == 1


def test_concurrent_issue_two_companies_independent(client: TestClient) -> None:
    """Different tenants issuing simultaneously must not affect each
    other's sequence — mirrors test_document_sequences.py's own
    cross-company isolation test, applied to the real Issue transaction."""
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import TenantContext, bind_tenant_scope, open_session
    from serviceflow.commercial import service as commercial_service

    h_a = _login(client, "Сервиз А", "a@a.bg")
    _ready_seller(client, h_a)
    oid_a = _order_with_lines(client, h_a)
    invoice_a = uuid_mod.UUID(_draft(client, h_a, oid_a))
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    _ready_seller(client, h_b)
    oid_b = _order_with_lines(client, h_b)
    invoice_b = uuid_mod.UUID(_draft(client, h_b, oid_b))

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    from serviceflow.customers.models import Customer  # noqa: F401 — ensures mapper import order

    owners = {}
    for db in open_session(url):
        for email in ("a@a.bg", "b@b.bg"):
            owner = db.scalar(select(User).where(User.email == email))
            assert owner is not None
            owners[email] = owner

    barrier = threading.Barrier(2)
    results: list[object] = [None, None]

    def run(index: int, email: str, invoice_id: uuid_mod.UUID) -> None:
        import datetime as dt

        owner = owners[email]
        ctx = TenantContext(company_id=owner.company_id, user_id=owner.id, is_owner=True)
        db = _new_session(url)
        bind_tenant_scope(db, owner.company_id)
        try:
            barrier.wait(timeout=10)
            invoice = commercial_service.issue(db, ctx, invoice_id, dt.date(2026, 3, 1))
            results[index] = invoice.number
        except BaseException as exc:  # noqa: BLE001 — captured, asserted below
            results[index] = exc
        finally:
            db.close()

    threads = [
        threading.Thread(target=run, args=(0, "a@a.bg", invoice_a)),
        threading.Thread(target=run, args=(1, "b@b.bg", invoice_b)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    for i, result in enumerate(results):
        assert not isinstance(result, BaseException), f"thread {i} failed: {result!r}"
    # Each tenant starts its own fresh series — unaffected by the other.
    assert results == [1, 1]


# --- Immutability ------------------------------------------------------


def test_patch_rejected_on_issued_invoice(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)
    assert _issue(client, h, invoice_id).status_code == 200

    resp = client.patch(f"/api/v1/invoices/{invoice_id}", headers=h, json={
        "lines": [{"description": "опит за промяна", "qty": 1, "unit_price": "1",
                  "source": "manual"}],
    })
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.not_draft"


def test_seller_snapshot_survives_later_company_edit(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    original_seller = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()["seller"]

    client.patch("/api/v1/company/requisites", headers=h,
                json={"address": "гр. Варна, друг адрес", "eik": "175074752"})

    seller_after_edit = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()["seller"]
    assert seller_after_edit == original_seller


def test_vat_registered_seller_snapshot_survives_later_requisites_edit(
    client: TestClient,
) -> None:
    h = _login(client)
    _ready_vat_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    original = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()
    original_seller = original["seller"]
    assert original_seller == {
        "name": "Сервиз А", "address": "гр. София, ул. Примерна 1",
        "eik": VALID_EIK, "vat_registered": True, "vat_number": f"BG{VALID_EIK}",
    }

    # Flip vat_registered off and change the ЕИК after Issue.
    client.patch("/api/v1/company/requisites", headers=h,
                json={"address": "гр. Варна, друг адрес", "eik": "175074752",
                     "vat_registered": False})

    after_edit = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()
    assert after_edit["seller"] == original_seller
    assert after_edit["vat_mode"] == "registered"
    assert after_edit["vat"] == original["vat"]
    assert after_edit["gross"] == original["gross"]


def test_buyer_snapshot_survives_later_customer_edit(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order(client, h, customer_name="Мария Иванова")
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"name": "Дисплей", "qty": 1, "unit_cost": "60", "unit_price": "100"})
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    original_buyer = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()["buyer"]
    assert original_buyer == {"name": "Мария Иванова"}

    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.service_orders.models import ServiceOrder

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        order = db.get(ServiceOrder, uuid_mod.UUID(oid))
        assert order is not None
        customer_id = order.customer_id

    client.patch(f"/api/v1/customers/{customer_id}", headers=h, json={"name": "Различно Име"})

    buyer_after_edit = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()["buyer"]
    assert buyer_after_edit == original_buyer


def test_non_vat_company_buyer_snapshot_survives_later_customer_edits(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="Пример ЕООД", is_company=True,
                            vat_registered=False, company_address="гр. Пловдив",
                            company_eik=VALID_EIK)
    cid = _customer_id_for_order(oid)
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    original_buyer = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()["buyer"]
    assert original_buyer == {
        "name": "Пример ЕООД", "address": "гр. Пловдив", "eik": VALID_EIK,
        "vat_registered": False,
    }

    # Edit name, address, EIK, and flip vat_registered to True with a number —
    # none of it may retroactively change the already-issued snapshot.
    client.patch(f"/api/v1/customers/{cid}", headers=h, json={
        "name": "Друго Име ООД",
        "vat_registered": True,
        "company_requisites": {
            "address": "гр. Бургас", "eik": "175074752", "vat_number": "BG175074752",
        },
    })

    buyer_after_edit = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()["buyer"]
    assert buyer_after_edit == original_buyer


def test_vat_registered_company_buyer_snapshot_survives_vat_number_edit(
    client: TestClient,
) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="ДДС ЕООД", is_company=True,
                            vat_registered=True, vat_number="BG130489869")
    cid = _customer_id_for_order(oid)
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    original_buyer = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()["buyer"]
    assert original_buyer["vat_number"] == "BG130489869"

    client.patch(f"/api/v1/customers/{cid}", headers=h, json={
        "company_requisites": {
            "address": "гр. Пловдив", "eik": VALID_EIK, "vat_number": "BG175074752",
        },
    })

    buyer_after_edit = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()["buyer"]
    assert buyer_after_edit == original_buyer
    assert buyer_after_edit["vat_number"] == "BG130489869"


def test_cross_tenant_company_buyer_data_not_visible(client: TestClient) -> None:
    """The buyer snapshot is resolved through customers_contracts, which is
    itself scoped by TenantContext — this proves an issued company-buyer
    invoice is invisible cross-tenant end to end, same as the plain
    tenant-isolation test but exercising the company-buyer code path."""
    h_a = _login(client, "Сервиз А", "a@a.bg")
    _ready_seller(client, h_a)
    oid = _order_with_lines(client, h_a, customer_name="Фирма А ЕООД", is_company=True,
                            vat_registered=False)
    invoice_id = _draft(client, h_a, oid)
    assert _issue(client, h_a, invoice_id).status_code == 200
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    resp = client.get(f"/api/v1/invoices/{invoice_id}", headers=h_b)
    assert resp.status_code == 404
