"""Приемо-предавателен протокол: minimal intake variant (docs/13 Етап-2 scope,
docs/02 §13). A broken protocol is a launch blocker (docs/10 §5) — verify it
actually renders valid, non-trivial PDF content, not just a 200 status."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _login(client: TestClient, company: str = "Сервиз Компютри ООД",
           email: str = "a@a.bg") -> dict[str, str]:
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, company, "Owner", email, "парола-123")
    me = client.post("/api/v1/auth/login",
                     json={"email": email, "password": "парола-123"}).json()
    return {"X-CSRF-Token": str(me["csrf_token"])}


def _order_with_accessories(client: TestClient, h: dict[str, str]) -> str:
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван Петров", "phone": "0888111222"}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone",
        "field_values": {"brand": "Samsung", "model": "Galaxy S22",
                         "imei": "356985061234567"},
    }).json()["id"]
    oid = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Не се включва след падане",
    }).json()["id"]
    client.post(f"/api/v1/orders/{oid}/accessories", headers=h,
               json={"name": "Зарядно", "qty": 1})
    client.post(f"/api/v1/orders/{oid}/accessories", headers=h,
               json={"name": "Кутия", "qty": 1})
    return str(oid)


def test_protocol_pdf_renders_with_expected_content(client: TestClient) -> None:
    h = _login(client)
    oid = _order_with_accessories(client, h)

    r = client.get(f"/api/v1/orders/{oid}/protocol.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "protokol-" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF")
    assert len(r.content) > 2000  # a real rendered page, not an empty shell

    # Extract text to prove the actual order data made it onto the page, not
    # just that SOME pdf was produced.
    text = _extract_pdf_text(r.content)
    assert "Иван Петров" in text
    assert "Samsung" in text
    assert "356985061234567" in text
    assert "Не се включва" in text
    assert "Зарядно" in text
    assert "Кутия" in text
    assert "Клиент" in text
    assert "Приел" in text


def test_protocol_pdf_handles_no_accessories(client: TestClient) -> None:
    h = _login(client)
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Мария", "phone": "0888999888"}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Кафемашина"},
    }).json()["id"]
    oid = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Не прави кафе",
    }).json()["id"]

    r = client.get(f"/api/v1/orders/{oid}/protocol.pdf")
    assert r.status_code == 200
    text = _extract_pdf_text(r.content)
    assert "(няма)" in text


def test_delivery_variant_not_yet_available(client: TestClient) -> None:
    h = _login(client)
    oid = _order_with_accessories(client, h)
    r = client.get(f"/api/v1/orders/{oid}/protocol.pdf?type=delivery")
    assert r.status_code == 501
    assert r.json()["detail"]["message_key"] == "errors.protocol.delivery_not_available"


def test_invalid_type_rejected(client: TestClient) -> None:
    h = _login(client)
    oid = _order_with_accessories(client, h)
    r = client.get(f"/api/v1/orders/{oid}/protocol.pdf?type=nonsense")
    assert r.status_code == 400


def test_protocol_pdf_reflects_company_requisites_set_via_settings(client: TestClient) -> None:
    """The protocol PDF has always read `company.requisites.get("address"/
    "phone")` (service_orders/router.py), but until the Company Legal
    Requisites slice, nothing could ever set them - every company's
    protocol rendered blank there. Proves the two stay wired together."""
    h = _login(client)
    client.patch("/api/v1/company/requisites", headers=h,
                json={"address": "гр. София, бул. Тестов 5", "phone": "021234567"})
    oid = _order_with_accessories(client, h)

    r = client.get(f"/api/v1/orders/{oid}/protocol.pdf")
    assert r.status_code == 200
    text = _extract_pdf_text(r.content)
    assert "гр. София, бул. Тестов 5" in text
    assert "021234567" in text


def test_protocol_is_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid = _order_with_accessories(client, h_a)
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    assert client.get(f"/api/v1/orders/{oid}/protocol.pdf").status_code == 404


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """fpdf2 shows text via glyph-index CID codes, not literal Unicode bytes in
    the content stream — a hand-rolled extractor would have to hunt for the
    embedded ToUnicode CMap, so this uses pypdf (dev-only), which already does
    that correctly; verified against a probe PDF before writing this test."""
    import io

    from pypdf import PdfReader

    return "".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf_bytes)).pages)
