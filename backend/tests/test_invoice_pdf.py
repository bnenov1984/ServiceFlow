"""Issued Invoice PDF (docs/ACCOUNTANT_REVIEW.md 'RepairFlow Invoice V1
Freeze' §5/§11, §4 B1, §6): GET /invoices/{id}/invoice.pdf. Read-only —
generated fresh from the frozen Invoice/InvoiceLine snapshot on every
request, never from live Company/Customer data. Covers individual and
domestic company (VAT-registered or not) buyers, and a seller that is
non-VAT-registered or VAT-registered at the single standard rate. See
commercial/pdf.py's module docstring for the exact rationale."""

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


def _ready_vat_seller(client: TestClient, h: dict[str, str], eik: str = VALID_EIK) -> None:
    _ready_seller(client, h, eik)
    resp = client.patch("/api/v1/company/requisites", headers=h, json={"vat_registered": True})
    assert resp.status_code == 200, resp.text


def _order(client: TestClient, h: dict[str, str], *,
          customer_name: str = "Иван Петров", is_company: bool = False,
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
    cid = client.post("/api/v1/customers", headers=h, json=payload).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]
    return str(client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Не се включва",
    }).json()["id"])


def _catalog_item(client: TestClient, h: dict[str, str], *, kind: str,
                  name: str, sale_price: str) -> str:
    r = client.post("/api/v1/catalog-items", headers=h,
                    json={"kind": kind, "name": name, "unit": "pcs", "sale_price": sale_price})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def _technician_id(client: TestClient, h: dict[str, str]) -> str:
    """order-workflow-revamp WP-G (Q2a): diagnostics now requires a
    technician on file — the Owner is itself a valid one (Q22)."""
    return str(next(u["id"] for u in client.get("/api/v1/users", headers=h).json()
                    if u["is_owner"]))


def _order_with_lines(client: TestClient, h: dict[str, str], **kwargs: object) -> str:
    oid = _order(client, h, **kwargs)  # type: ignore[arg-type]
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    part_id = _catalog_item(client, h, kind="part", name="Дисплей", sale_price="100")
    labor_id = _catalog_item(client, h, kind="labor", name="Смяна на дисплей", sale_price="50")
    client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
               json={"catalog_item_id": part_id})
    client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
               json={"catalog_item_id": labor_id})
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


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Same technique as test_protocol.py's helper — fpdf2 shows text via
    glyph-index CID codes, not literal Unicode bytes; pypdf (dev-only)
    already resolves the embedded ToUnicode CMap correctly."""
    import io

    from pypdf import PdfReader

    return "".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf_bytes)).pages)


# --- Happy path / content ------------------------------------------------


def test_issued_invoice_pdf_returns_200_application_pdf(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "invoice-0000000001.pdf" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF")
    assert len(r.content) > 2000


def test_canonical_invoice_number_rendered_unchanged(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    assert "0000000001" in text
    assert "№ 1" not in text  # never the un-padded int


def test_issued_at_rendered(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    assert "Дата на издаване:" in text


def test_tax_event_date_rendered_without_timezone_shift(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id, tax_event_date="2026-01-01")

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    # A UTC-shift bug would render 31.12.2025 (or 02.01.2026) instead.
    assert "01.01.2026" in text
    assert "31.12.2025" not in text
    assert "02.01.2026" not in text


def test_frozen_seller_identity_rendered(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    assert "Сервиз А" in text
    assert "гр. София, ул. Примерна 1" in text
    assert VALID_EIK in text
    assert "ДОСТАВЧИК" in text


def test_frozen_buyer_name_rendered(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h, customer_name="Мария Иванова")

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    assert "Мария Иванова" in text
    assert "ПОЛУЧАТЕЛ" in text


def test_non_vat_company_buyer_pdf_renders_address_and_eik(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h, customer_name="Пример ЕООД", is_company=True,
                                 vat_registered=False, company_address="гр. Пловдив")

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    assert "Пример ЕООД" in text
    assert "гр. Пловдив" in text
    assert VALID_EIK in text
    assert "ДДС №:" not in text


def test_vat_registered_company_buyer_pdf_renders_vat_number(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h, customer_name="ДДС ЕООД", is_company=True,
                                 vat_registered=True, vat_number="BG130489869")

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    assert "ДДС ЕООД" in text
    assert "ДДС №:" in text
    assert "BG130489869" in text


def test_line_columns_rendered(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    assert "Дисплей" in text
    assert "Смяна на дисплей" in text
    assert "100.00" in text  # part unit price
    assert "50.00" in text  # labor unit price


def test_frozen_totals_rendered(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    assert "Данъчна основа" in text
    assert "150.00" in text  # net == gross for Phase A (100 + 50)
    assert "Общо" in text


def test_non_vat_wording_rendered(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    assert "ДДС: не се начислява" in text
    assert "ДДС 0%" not in text
    assert "0%" not in text


def test_vat_registered_seller_pdf_renders_vat_number_and_amount(client: TestClient) -> None:
    h = _login(client)
    _ready_vat_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    assert f"ДДС №: BG{VALID_EIK}" in text
    assert "ДДС 20%:" in text
    assert "30.00" in text  # 150.00 net * 0.20
    assert "180.00" in text  # gross
    assert "ДДС: не се начислява" not in text


def test_cyrillic_survives_extraction(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    text = _extract_pdf_text(r.content)
    assert "ФАКТУРА" in text
    assert "ДОСТАВЧИК" in text
    assert "ПОЛУЧАТЕЛ" in text


# --- Validation / status ---------------------------------------------------


def test_draft_invoice_pdf_rejected(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h)
    invoice_id = _draft(client, h, oid)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.invoices.not_issued"


def test_missing_invoice_returns_existing_not_found_shape(client: TestClient) -> None:
    h = _login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/api/v1/invoices/{fake_id}/invoice.pdf", headers=h)
    assert r.status_code == 404
    assert r.json()["detail"]["message_key"] == "errors.invoices.not_found"


def test_wrong_tenant_cannot_download(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    _ready_seller(client, h_a)
    invoice_id = _issued_invoice(client, h_a)
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h_b)
    assert r.status_code == 404


# --- Immutability (mandatory) -----------------------------------------------


def test_pdf_reflects_frozen_snapshot_not_live_master_data(client: TestClient) -> None:
    """The core proof this slice exists for: the PDF is a representation of
    the issued document, not a fresh report over mutable Company/Customer
    data. Edits made after Issue must never appear in the PDF."""
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.service_orders.models import ServiceOrder

    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="Оригинално Име")
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    original = _extract_pdf_text(
        client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h).content,
    )
    assert "Сервиз А" in original
    assert "гр. София, ул. Примерна 1" in original
    assert VALID_EIK in original
    assert "Оригинално Име" in original

    # Change Company.name/requisites after Issue.
    client.patch("/api/v1/company/requisites", headers=h,
                json={"address": "гр. Варна, съвсем друг адрес", "eik": "175074752"})

    # Change Customer.name after Issue.
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        order = db.get(ServiceOrder, oid)
        assert order is not None
        customer_id = order.customer_id
    client.patch(f"/api/v1/customers/{customer_id}", headers=h, json={"name": "Ново Име"})

    after_edit = _extract_pdf_text(
        client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h).content,
    )
    # Old, frozen snapshot values still present.
    assert "Сервиз А" in after_edit
    assert "гр. София, ул. Примерна 1" in after_edit
    assert VALID_EIK in after_edit
    assert "Оригинално Име" in after_edit
    # New, live-edited values must never leak in.
    assert "гр. Варна, съвсем друг адрес" not in after_edit
    assert "175074752" not in after_edit
    assert "Ново Име" not in after_edit
    assert after_edit == original


def test_company_buyer_pdf_frozen_after_customer_edit(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order_with_lines(client, h, customer_name="Пример ЕООД", is_company=True,
                            vat_registered=True, company_address="гр. Пловдив",
                            company_eik=VALID_EIK, vat_number="BG130489869")
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    original = _extract_pdf_text(
        client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h).content,
    )
    assert "Пример ЕООД" in original
    assert "BG130489869" in original

    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.service_orders.models import ServiceOrder

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        order = db.get(ServiceOrder, oid)
        assert order is not None
        customer_id = order.customer_id
    client.patch(f"/api/v1/customers/{customer_id}", headers=h, json={
        "name": "Друго Име ООД",
        "company_requisites": {
            "address": "гр. Бургас", "eik": "175074752", "vat_number": "BG175074752",
        },
    })

    after_edit = _extract_pdf_text(
        client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h).content,
    )
    assert after_edit == original
    assert "Друго Име ООД" not in after_edit
    assert "BG175074752" not in after_edit


def test_vat_registered_seller_pdf_frozen_after_requisites_edit(client: TestClient) -> None:
    h = _login(client)
    _ready_vat_seller(client, h)
    invoice_id = _issued_invoice(client, h)

    original = _extract_pdf_text(
        client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h).content,
    )
    assert f"ДДС №: BG{VALID_EIK}" in original
    assert "30.00" in original

    # Flip vat_registered off and change the ЕИК after Issue.
    client.patch("/api/v1/company/requisites", headers=h,
                json={"address": "гр. Варна, друг адрес", "eik": "175074752",
                     "vat_registered": False})

    after_edit = _extract_pdf_text(
        client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h).content,
    )
    assert after_edit == original
    assert "175074752" not in after_edit


# --- Pagination / robustness -------------------------------------------


def test_multiple_lines_all_rendered(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    for i in range(5):
        item_id = _catalog_item(client, h, kind="part", name=f"Част {i}", sale_price="10")
        client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                   json={"catalog_item_id": item_id})
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    assert r.status_code == 200
    text = _extract_pdf_text(r.content)
    for i in range(5):
        assert f"Част {i}" in text


def test_long_company_buyer_address_wraps_without_failing(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    long_address = (
        "гр. София, ж.к. Много Дълъг Квартал, бул. Изключително Дългото Име На Булеварда "
        "№ 123, вход Б, етаж 7, апартамент 45, до автосервиз до голямата бензиностанция"
    )
    oid = _order_with_lines(client, h, customer_name="Пример ЕООД", is_company=True,
                            vat_registered=False, company_address=long_address)
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")
    text = _extract_pdf_text(r.content)
    assert "Много Дълъг Квартал" in text


def test_long_description_wraps_without_failing(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    long_description = (
        "Много дълго описание на извършена дейност, което трябва да се пренесе на "
        "няколко реда в таблицата на фактурата, без да преля извън страницата или "
        "да развали PDF документа по какъвто и да е начин."
    )
    labor_id = _catalog_item(client, h, kind="labor", name=long_description, sale_price="10")
    client.post(f"/api/v1/orders/{oid}/labor-lines", headers=h,
               json={"catalog_item_id": labor_id})
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")
    text = _extract_pdf_text(r.content)
    assert "Много дълго описание" in text


def test_large_invoice_paginates_without_corrupting_pdf(client: TestClient) -> None:
    h = _login(client)
    _ready_seller(client, h)
    oid = _order(client, h)
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "diagnostics", "technician_id": _technician_id(client, h)})
    for i in range(60):
        item_id = _catalog_item(client, h, kind="part",
                                name=f"Компонент номер {i:03d} за тестова страница",
                                sale_price="5")
        client.post(f"/api/v1/orders/{oid}/part-lines", headers=h,
                   json={"catalog_item_id": item_id})
    invoice_id = _draft(client, h, oid)
    _issue(client, h, invoice_id)

    r = client.get(f"/api/v1/invoices/{invoice_id}/invoice.pdf", headers=h)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")

    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) > 1  # 60 lines must not fit a single A4 page

    text = _extract_pdf_text(r.content)
    assert "Компонент номер 000" in text
    assert "Компонент номер 059" in text
    assert "Общо" in text  # totals block survived pagination, not clipped
