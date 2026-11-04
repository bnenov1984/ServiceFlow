"""Attachments: upload validation, re-encoding/thumbnails, authorized streaming,
soft delete, tenant isolation (docs/01 §Attachment, docs/11 §3)."""

import io
import itertools
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)

# order-workflow-revamp WP-B (Q7): a second individual customer with the same
# phone is now blocked, so `_order()` — called multiple times per test with no
# caller-supplied uniqueness — needs a phone that's guaranteed distinct on
# every call, never a fixed literal (same pattern as test_invoices.py).
_phone_seq = itertools.count(100000)


def _unique_phone() -> str:
    return f"0888{next(_phone_seq)}"


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
        "customer_id": cid, "asset_id": aid, "complaint": "x",
    }).json()["id"])


def _jpeg_bytes(size: tuple[int, int] = (800, 600), color: str = "red") -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _png_bytes() -> bytes:
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_upload_jpeg_reencodes_and_generates_thumbnail(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    r = client.post(
        f"/api/v1/orders/{oid}/attachments", headers=h,
        files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"stage": "reception", "caption": "Оглед при приемане"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "photo"
    assert body["mime"] == "image/jpeg"
    assert body["has_thumbnail"] is True
    assert body["stage"] == "reception"

    full = client.get(f"/api/v1/attachments/{body['id']}/file")
    assert full.status_code == 200
    assert full.headers["content-type"] == "image/jpeg"
    full_img = Image.open(io.BytesIO(full.content))
    assert full_img.size == (800, 600)

    thumb = client.get(f"/api/v1/attachments/{body['id']}/file?thumb=true")
    assert thumb.status_code == 200
    thumb_img = Image.open(io.BytesIO(thumb.content))
    assert max(thumb_img.size) <= 320
    assert thumb.content != full.content


def test_png_is_normalized_to_jpeg(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    r = client.post(
        f"/api/v1/orders/{oid}/attachments", headers=h,
        files={"file": ("photo.png", _png_bytes(), "image/png")},
        data={"stage": "progress"},
    )
    assert r.status_code == 201
    assert r.json()["mime"] == "image/jpeg"  # re-encoded regardless of source format


def test_pdf_is_stored_as_is_and_classified_as_document(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    r = client.post(
        f"/api/v1/orders/{oid}/attachments", headers=h,
        files={"file": ("estimate.pdf", pdf_bytes, "application/pdf")},
        data={"stage": "other"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "document"
    assert body["mime"] == "application/pdf"
    assert body["has_thumbnail"] is False

    r = client.get(f"/api/v1/attachments/{body['id']}/file")
    assert r.content == pdf_bytes  # untouched, unlike images


def test_unsupported_type_rejected_by_magic_bytes(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    r = client.post(
        f"/api/v1/orders/{oid}/attachments", headers=h,
        files={"file": ("evil.jpg", b"MZ\x90\x00this is actually an exe", "image/jpeg")},
        data={"stage": "other"},
    )
    assert r.status_code == 415
    assert r.json()["detail"]["message_key"] == "errors.attachments.unsupported_type"


def test_oversized_file_rejected(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    huge = _jpeg_bytes(size=(4000, 3000))
    from serviceflow.config import get_settings
    get_settings.cache_clear()
    import os as _os
    _os.environ["SERVICEFLOW_ATTACHMENTS_MAX_BYTES"] = "1000"
    get_settings.cache_clear()
    try:
        r = client.post(
            f"/api/v1/orders/{oid}/attachments", headers=h,
            files={"file": ("big.jpg", huge, "image/jpeg")},
            data={"stage": "other"},
        )
        assert r.status_code == 413
    finally:
        del _os.environ["SERVICEFLOW_ATTACHMENTS_MAX_BYTES"]
        get_settings.cache_clear()


def test_invalid_stage_rejected(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    r = client.post(
        f"/api/v1/orders/{oid}/attachments", headers=h,
        files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"stage": "not_a_stage"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["message_key"] == "errors.attachments.invalid_stage"


def test_soft_delete_hides_from_list_and_writes_timeline(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    aid = client.post(
        f"/api/v1/orders/{oid}/attachments", headers=h,
        files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"stage": "other"},
    ).json()["id"]

    assert len(client.get(f"/api/v1/orders/{oid}/attachments").json()) == 1
    r = client.delete(f"/api/v1/attachments/{aid}", headers=h)
    assert r.status_code == 200
    assert client.get(f"/api/v1/orders/{oid}/attachments").json() == []
    assert client.get(f"/api/v1/attachments/{aid}/file").status_code == 404

    events = [e["event_type"] for e in client.get(f"/api/v1/orders/{oid}/timeline").json()]
    assert "attachment_added" in events
    assert "attachment_deleted" in events


def test_seq_increments_per_order_in_upload_order_and_survives_delete(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    order_number = client.get(f"/api/v1/orders/{oid}", headers=h).json()["number"]

    first = client.post(
        f"/api/v1/orders/{oid}/attachments", headers=h,
        files={"file": ("a.jpg", _jpeg_bytes(), "image/jpeg")}, data={"stage": "reception"},
    ).json()
    second = client.post(
        f"/api/v1/orders/{oid}/attachments", headers=h,
        files={"file": ("b.jpg", _jpeg_bytes(), "image/jpeg")}, data={"stage": "progress"},
    ).json()
    assert first["display_name"] == f"{order_number}_1.jpg"
    assert second["display_name"] == f"{order_number}_2.jpg"

    client.delete(f"/api/v1/attachments/{first['id']}", headers=h)
    third = client.post(
        f"/api/v1/orders/{oid}/attachments", headers=h,
        files={"file": ("c.jpg", _jpeg_bytes(), "image/jpeg")}, data={"stage": "other"},
    ).json()
    # #1 was deleted, not reused or renumbered — the next upload is #3, not #2.
    assert third["display_name"] == f"{order_number}_3.jpg"


def test_seq_is_independent_per_order(client: TestClient) -> None:
    h = _login(client)
    oid_a = _order(client, h)
    oid_b = _order(client, h)
    a = client.post(
        f"/api/v1/orders/{oid_a}/attachments", headers=h,
        files={"file": ("a.jpg", _jpeg_bytes(), "image/jpeg")}, data={"stage": "other"},
    ).json()
    b = client.post(
        f"/api/v1/orders/{oid_b}/attachments", headers=h,
        files={"file": ("b.jpg", _jpeg_bytes(), "image/jpeg")}, data={"stage": "other"},
    ).json()
    assert a["display_name"].endswith("_1.jpg")
    assert b["display_name"].endswith("_1.jpg")
    assert a["display_name"] != b["display_name"]  # different order numbers


def test_download_filename_uses_order_number_and_seq(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    order_number = client.get(f"/api/v1/orders/{oid}", headers=h).json()["number"]
    aid = client.post(
        f"/api/v1/orders/{oid}/attachments", headers=h,
        files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")}, data={"stage": "other"},
    ).json()["id"]

    r = client.get(f"/api/v1/attachments/{aid}/file")
    assert f'filename="{order_number}_1.jpg"' in r.headers["content-disposition"]


def test_attachments_are_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid = _order(client, h_a)
    aid = client.post(
        f"/api/v1/orders/{oid}/attachments", headers=h_a,
        files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"stage": "other"},
    ).json()["id"]
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    assert client.get(f"/api/v1/attachments/{aid}/file").status_code == 404
    assert client.get(f"/api/v1/orders/{oid}/attachments").status_code == 404
