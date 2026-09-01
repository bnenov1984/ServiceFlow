"""Invoice Annulment (Wave 6 Issue 30, docs/ACCOUNTANT_REVIEW.md §7 case A —
ЗДДС чл. 116): POST /invoices/{id}/annul. A pure status+metadata transition
on an already-issued invoice — never edits, deletes, or renumbers it, never
touches the frozen seller/buyer/lines/net/vat/gross, never populates
annuls_invoice_id (reserved for a future reissue-linkage feature), never
touches any Payment. See commercial/service.py's `annul()`."""

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


def _order(client: TestClient, h: dict[str, str], *,
          customer_name: str = "Иван Петров") -> str:
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": customer_name, "phone": "0888111222",
    }).json()["id"]
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
          tax_event_date: str = TAX_EVENT_DATE) -> str:
    resp = client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=h,
                       json={"tax_event_date": tax_event_date})
    assert resp.status_code == 200, resp.text
    return invoice_id


def _issued_invoice(client: TestClient, h: dict[str, str], **kwargs: object) -> str:
    oid = _order_with_lines(client, h, **kwargs)  # type: ignore[arg-type]
    invoice_id = _draft(client, h, oid)
    return _issue(client, h, invoice_id)


def _annul(client: TestClient, h: dict[str, str], invoice_id: str,
          reason: str = "Грешно избран клиент") -> "object":
    return client.post(f"/api/v1/invoices/{invoice_id}/annul", headers=h,
                       json={"reason": reason})


def _timeline_events(order_id: str, event_type: str,
                     owner_email: str = "a@a.bg") -> list[object]:
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.timeline.models import TimelineEvent

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == owner_email))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        return list(db.scalars(select(TimelineEvent).where(
            TimelineEvent.order_id == uuid_mod.UUID(order_id),
            TimelineEvent.event_type == event_type,
        )))
    raise AssertionError("unreachable")


def _sequence_current(company_id: uuid_mod.UUID) -> int | None:
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


# --- Happy path -----------------------------------------------------------


def test_issued_invoice_can_be_annulled(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    resp = _annul(client, h, invoice_id, reason="Грешен клиент избран по невнимание")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "annulled"
    assert body["annul_reason"] == "Грешен клиент избран по невнимание"
    assert body["annulled_at"] is not None

    events = _timeline_events(oid, "invoice_annulled")
    assert len(events) == 1
    assert events[0].data["invoice_id"] == invoice_id


def test_annulled_invoice_reflected_on_get(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)
    _annul(client, h, invoice_id)

    resp = client.get(f"/api/v1/invoices/{invoice_id}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "annulled"


# --- Invariants: number/snapshot/lines/totals/payments unchanged ----------


def test_annulment_preserves_number_snapshots_totals_and_lines(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="Мария Иванова")
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    before = client.get(f"/api/v1/invoices/{invoice_id}", headers=h).json()

    resp = _annul(client, h, invoice_id)
    assert resp.status_code == 200, resp.text
    after = resp.json()

    assert after["number"] == before["number"]
    assert after["issued_at"] == before["issued_at"]
    assert after["tax_event_date"] == before["tax_event_date"]
    assert after["seller"] == before["seller"]
    assert after["buyer"] == before["buyer"]
    assert after["net"] == before["net"]
    assert after["vat"] == before["vat"]
    assert after["gross"] == before["gross"]
    assert after["lines"] == before["lines"]


def test_annulment_does_not_populate_annuls_invoice_id(client: TestClient) -> None:
    """annuls_invoice_id is reserved for a future reissue-linkage feature —
    not exposed by InvoiceDetailOut at all, so this proves the row itself
    stays NULL via a direct DB read."""
    from sqlalchemy import select

    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.commercial.models import Invoice

    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)
    _annul(client, h, invoice_id)

    company_id = _owner_company_id()
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        bind_tenant_scope(db, company_id)
        invoice = db.scalar(select(Invoice).where(Invoice.id == uuid_mod.UUID(invoice_id)))
        assert invoice is not None
        assert invoice.annuls_invoice_id is None


def test_annulment_does_not_release_or_allow_number_reuse(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id_1 = _issued_invoice(client, h)
    _annul(client, h, invoice_id_1)

    oid_2 = _order_with_lines(client, h)
    invoice_id_2 = _draft(client, h, oid_2)
    resp = _issue(client, h, invoice_id_2)
    body = client.get(f"/api/v1/invoices/{resp}", headers=h).json()
    # The next invoice still gets the next sequential number (2), never a
    # reused/gapped value — annulling #1 did not touch the sequence.
    assert body["number"] == 2


def test_annulment_does_not_change_payments(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    client.post(f"/api/v1/orders/{oid}/payments", headers=h,
               json={"amount": "50", "method": "cash"})
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    balance_before = client.get(f"/api/v1/orders/{oid}", headers=h).json()["balance"]
    _annul(client, h, invoice_id)
    balance_after = client.get(f"/api/v1/orders/{oid}", headers=h).json()["balance"]
    assert balance_after == balance_before


# --- Invalid state transitions --------------------------------------------


def test_draft_cannot_be_annulled(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    resp = _annul(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.annul_not_issued"


def test_already_annulled_cannot_be_annulled_again(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)
    assert _annul(client, h, invoice_id).status_code == 200

    resp = _annul(client, h, invoice_id)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.invoices.already_annulled"


def test_blank_reason_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    resp = client.post(f"/api/v1/invoices/{invoice_id}/annul", headers=h, json={"reason": ""})
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_whitespace_only_reason_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    resp = client.post(f"/api/v1/invoices/{invoice_id}/annul", headers=h, json={"reason": "   "})
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_missing_invoice_returns_404(client: TestClient) -> None:
    h = _login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = _annul(client, h, fake_id)
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.invoices.not_found"


def test_wrong_tenant_returns_404(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    _ready_seller(client, h_a)
    invoice_id = _issued_invoice(client, h_a)
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    resp = _annul(client, h_b, invoice_id)
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.invoices.not_found"


# --- Authorization ----------------------------------------------------------


def test_worker_forbidden(client: TestClient) -> None:
    h_owner = _login(client)
    _ready_seller(client, h_owner)
    invoice_id = _issued_invoice(client, h_owner)
    client.post("/api/v1/users", headers=h_owner,
               json={"name": "Иво", "email": "ivo@a.bg", "password": "парола-за-иво-123"})
    client.post("/api/v1/auth/logout", headers=h_owner)

    me = client.post("/api/v1/auth/login",
                     json={"email": "ivo@a.bg", "password": "парола-за-иво-123"}).json()
    h_worker = {"X-CSRF-Token": str(me["csrf_token"])}
    resp = _annul(client, h_worker, invoice_id)
    assert resp.status_code == 403
    assert resp.json()["detail"]["message_key"] == "errors.auth.owner_required"

    # The invoice must remain untouched by the rejected attempt.
    body = client.get(f"/api/v1/invoices/{invoice_id}", headers=h_owner).json()
    assert body["status"] == "issued"


def test_missing_csrf_forbidden(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    resp = client.post(f"/api/v1/invoices/{invoice_id}/annul",
                       json={"reason": "Грешка"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["message_key"] == "errors.auth.csrf"


def test_suspended_subscription_blocked(client: TestClient) -> None:
    from sqlalchemy import select

    from business_os.identity.models import Company, User
    from business_os.shared_kernel.db import open_session

    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        company = db.get(Company, owner.company_id)
        assert company is not None
        company.subscription_state = "suspended"
        db.commit()

    resp = _annul(client, h, invoice_id)
    assert resp.status_code == 402
    assert resp.json()["detail"]["message_key"] == "errors.subscription.mutations_blocked"


# --- PDF (issued + annulled) ------------------------------------------------


def test_annulled_invoice_pdf_still_available(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)
    _annul(client, h, invoice_id, reason="Грешно избран клиент")

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_annulled_invoice_pdf_shows_marker_date_and_reason(client: TestClient) -> None:
    import io

    from pypdf import PdfReader

    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)
    _annul(client, h, invoice_id, reason="Дублирана фактура по невнимание")

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(r.content)).pages)
    assert "АНУЛИРАНА" in text
    assert "Дата на анулиране:" in text
    assert "Дублирана фактура по невнимание" in text


def test_annulled_invoice_pdf_still_reads_frozen_data_only(client: TestClient) -> None:
    """Same proof as test_invoice_pdf.py's frozen-snapshot test, extended to
    the post-annulment state: later master-data edits must never leak in."""
    import io

    from pypdf import PdfReader
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.service_orders.models import ServiceOrder

    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="Оригинално Име")
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)
    _annul(client, h, invoice_id)

    def _text() -> str:
        r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
        return "".join(page.extract_text() for page in PdfReader(io.BytesIO(r.content)).pages)

    original = _text()
    assert "Оригинално Име" in original

    client.patch("/api/v1/company/requisites", headers=h,
                json={"address": "гр. Варна, друг адрес", "eik": "175074752"})
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        order = db.get(ServiceOrder, oid)
        assert order is not None
        customer_id = order.customer_id
    client.patch(f"/api/v1/customers/{customer_id}", headers=h, json={"name": "Ново Име"})

    after_edit = _text()
    assert after_edit == original
    assert "Ново Име" not in after_edit
    assert "175074752" not in after_edit


def test_draft_invoice_pdf_still_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.invoices.not_issued"


# --- Concurrency / locking ---------------------------------------------------


def test_concurrent_annul_same_invoice_exactly_one_succeeds(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    from sqlalchemy import select
    from sqlalchemy.orm import Session, sessionmaker

    from business_os.identity.models import User
    from business_os.shared_kernel.db import (
        TenantContext,
        bind_tenant_scope,
        get_engine,
        open_session,
    )
    from serviceflow.commercial import service as commercial_service

    h = _login(client)
    _ready_seller(client, h)
    invoice_id = uuid_mod.UUID(_issued_invoice(client, h))

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

    def _new_session() -> Session:
        return sessionmaker(bind=get_engine(url), expire_on_commit=False, class_=Session)()

    result_a: list[object] = []

    def run_a() -> None:
        session_a = _new_session()
        bind_tenant_scope(session_a, company_id)
        try:
            invoice = commercial_service.annul(session_a, ctx, invoice_id, "Причина А")
            result_a.append(invoice.status)
        except BaseException as exc:  # noqa: BLE001
            result_a.append(exc)
        finally:
            session_a.close()

    thread_a = threading.Thread(target=run_a)
    thread_a.start()
    assert reached_publish.wait(timeout=5), "thread A never reached the pre-commit hold point"

    result_b: list[object] = []

    def run_b() -> None:
        session_b = _new_session()
        bind_tenant_scope(session_b, company_id)
        try:
            commercial_service.annul(session_b, ctx, invoice_id, "Причина Б")
            result_b.append("succeeded")
        except BaseException as exc:  # noqa: BLE001
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

    assert result_a == ["annulled"]
    assert len(result_b) == 1
    assert isinstance(result_b[0], commercial_service.InvoiceError)
    assert result_b[0].message_key == "errors.invoices.already_annulled"
