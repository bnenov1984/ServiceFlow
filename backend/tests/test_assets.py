"""Assets: seed types, field validation, identifier extraction + duplicates, isolation."""

import os
import uuid
from typing import Any

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


def _customer(client: TestClient, h: dict[str, str], phone: str = "0888111222") -> str:
    return str(client.post("/api/v1/customers", headers=h,
                           json={"name": "Иван", "phone": phone}).json()["id"])


def test_seeded_asset_types(client: TestClient) -> None:
    _login(client)
    types = client.get("/api/v1/asset-types").json()
    assert [t["code"] for t in types] == ["phone", "vehicle", "laptop", "other"]
    phone = types[0]
    assert phone["name_bg"] == "Телефон"
    assert any(f.get("identifier_kind") == "imei" for f in phone["field_defs"])


def test_create_phone_asset_extracts_identifiers(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    r = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone",
        "field_values": {"brand": "Samsung", "model": "Galaxy S22",
                         "imei": "35-698506-123456 7"},
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["label"] == "Samsung Galaxy S22"
    assert body["duplicate_asset_ids"] == []

    # Same IMEI, different formatting → duplicate hint (second device, e.g. re-intake).
    r2 = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone",
        "field_values": {"brand": "Samsung", "model": "Galaxy S22",
                         "imei": "356985061234567"},
    })
    assert r2.json()["duplicate_asset_ids"] == [body["id"]]


def test_field_validation(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)

    def create(values: dict[str, Any]) -> Any:
        return client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
            "asset_type_code": "vehicle", "field_values": values,
        })

    r = create({"brand": "Volkswagen", "nonexistent": "x"})
    assert r.status_code == 400
    assert r.json()["detail"]["field_errors"] == [
        {"loc": "nonexistent", "type": "unknown_field"}
    ]

    assert create({"year": "не число"}).status_code == 400
    assert create({"brand": "Volkswagen", "model": "Golf", "year": 2019,
                   "reg_no": "ВН 1234 АК"}).status_code == 201

    r = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "няма-такъв", "field_values": {},
    })
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "unknown_asset_type"


def test_patch_preserves_legacy_choice_value_it_never_touches(client: TestClient) -> None:
    """Migration 0020 follow-up: an asset already holding a brand value from
    before `brand` became a choice field (e.g. "VW", never a valid entry in
    the new list) must stay editable and readable — an unrelated PATCH
    (mileage here) must not fail just because the stored brand is no longer
    in the current choices, and the legacy value itself must survive the
    round trip unchanged."""
    h = _login(client)
    cid = _customer(client, h)
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "Volkswagen", "model": "Golf"},
    }).json()["id"]

    # Simulate a pre-migration-0020 asset: overwrite the stored brand directly
    # (the API itself would reject "VW" now — this bypasses it on purpose to
    # reach the state a real pre-existing company's data is already in).
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.assets.models import Asset

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        asset = db.get(Asset, aid)
        assert asset is not None
        asset.field_values = {**asset.field_values, "brand": "VW"}
        db.commit()

    r = client.patch(f"/api/v1/assets/{aid}", headers=h, json={
        "field_values": {"model": "Golf 7"},
    })
    assert r.status_code == 200, r.text
    assert r.json()["field_values"]["brand"] == "VW"
    assert r.json()["field_values"]["model"] == "Golf 7"

    # The grandfather clause only covers the value already on file — trying
    # to *change* brand to a genuinely new, still-invalid value is still
    # rejected exactly like any other invalid choice.
    r2 = client.patch(f"/api/v1/assets/{aid}", headers=h, json={
        "field_values": {"brand": "NotARealMake"},
    })
    assert r2.status_code == 400
    assert r2.json()["detail"]["field_errors"] == [{"loc": "brand", "type": "invalid_choice"}]


@pytest.mark.parametrize("reg_no", ["CA5070BA", "CB1234PB", "PK1111BK", "TX9999CT"])
def test_field_validation_accepts_modern_reg_no_formats(client: TestClient, reg_no: str) -> None:
    """Modern BG plates use a two-letter regional prefix (e.g. Sofia "CA"/"CB")."""
    h = _login(client)
    cid = _customer(client, h)
    r = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "Volkswagen", "model": "Golf", "reg_no": reg_no},
    })
    assert r.status_code == 201, r.text


def test_patch_reextracts_identifiers(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "Volkswagen", "model": "Golf", "vin": "WVWZZZ1JZ3W386752"},
    }).json()["id"]

    r = client.patch(f"/api/v1/assets/{aid}", headers=h, json={
        "field_values": {"vin": "WAUZZZ8K9A123456"},
    })
    assert r.status_code == 200
    assert r.json()["row_version"] == 2

    # Verify via API: the old VIN's identifier row must have been replaced,
    # so it's free for a genuinely different vehicle to use.
    r2 = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "Volkswagen", "model": "Golf", "vin": "WVWZZZ1JZ3W386752"},
    })
    assert r2.status_code == 201, r2.text
    assert r2.json()["duplicate_asset_ids"] == []  # old VIN row was replaced

    # Wave 3 Issue 20: VIN is now hard-unique per tenant (not just a soft
    # duplicate hint) — a third vehicle claiming `aid`'s current VIN is
    # rejected outright, never created.
    r3 = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "Audi", "model": "A4", "vin": "WAUZZZ8K9A123456"},
    })
    assert r3.status_code == 409, r3.text
    assert r3.json()["detail"]["code"] == "vin_conflict"
    assert r3.json()["detail"]["conflicting_asset_id"] == aid


def test_assets_are_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    cid_a = _customer(client, h_a)
    aid = client.post(f"/api/v1/customers/{cid_a}/assets", headers=h_a, json={
        "asset_type_code": "phone", "field_values": {"brand": "Apple", "model": "13"},
    }).json()["id"]
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    assert client.get(f"/api/v1/assets/{aid}").status_code == 404
    assert client.get(f"/api/v1/customers/{cid_a}/assets").status_code == 404


# --- Wave 3 Issue 20: VIN-first identification + ownership history ---------

def _vehicle(client: TestClient, h: dict[str, str], cid: str, vin: str,
            model: str = "Golf") -> str:
    r = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "Volkswagen", "model": model, "vin": vin},
    })
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def test_by_vin_finds_asset_tenant_wide_regardless_of_customer(client: TestClient) -> None:
    h = _login(client)
    cid1 = _customer(client, h, "0888111222")
    cid2 = _customer(client, h, "0888333444")
    aid = _vehicle(client, h, cid1, "WVWZZZ1JZ3W386752")

    # A different customer's intake looks the VIN up — must still find it.
    r = client.get("/api/v1/assets/by-vin?vin=WVWZZZ1JZ3W386752", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == aid
    assert body["customer_id"] == cid1

    # Normalization-tolerant: spaces/dashes/case must not matter.
    r2 = client.get("/api/v1/assets/by-vin?vin=wvwzzz1jz3-w38 6752", headers=h)
    assert r2.status_code == 200
    assert r2.json()["id"] == aid

    r3 = client.get("/api/v1/assets/by-vin?vin=NOSUCHVIN0000000", headers=h)
    assert r3.status_code == 404
    assert r3.json()["detail"]["code"] == "not_found"

    # customer2 is otherwise unrelated — just proves the lookup didn't
    # accidentally require it.
    assert cid2


def test_by_vin_is_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    cid_a = _customer(client, h_a)
    _vehicle(client, h_a, cid_a, "WVWZZZ1JZ3W386752")
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    r = client.get("/api/v1/assets/by-vin?vin=WVWZZZ1JZ3W386752", headers=h_b)
    assert r.status_code == 404


def test_vin_uniqueness_is_scoped_per_tenant_not_global(client: TestClient) -> None:
    """Two different companies may legitimately have on-file the same VIN
    (e.g. both saw the car before it was sold across shops) — uniqueness is
    per (company_id, value_normalized), never a bare global constraint."""
    h_a = _login(client, "Сервиз А", "a@a.bg")
    cid_a = _customer(client, h_a)
    _vehicle(client, h_a, cid_a, "WVWZZZ1JZ3W386752")
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    cid_b = _customer(client, h_b)
    aid_b = _vehicle(client, h_b, cid_b, "WVWZZZ1JZ3W386752")
    assert aid_b


def test_transfer_owner_moves_current_owner_and_preserves_orders(client: TestClient) -> None:
    h = _login(client)
    cid1 = _customer(client, h, "0888111222")
    cid2 = _customer(client, h, "0888333444")
    aid = _vehicle(client, h, cid1, "WVWZZZ1JZ3W386752")
    order = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid1, "asset_id": aid, "complaint": "Смяна на масло",
    }).json()

    r = client.post(f"/api/v1/assets/{aid}/transfer-owner", headers=h,
                    json={"customer_id": cid2})
    assert r.status_code == 200, r.text
    assert r.json()["customer_id"] == cid2
    assert r.json()["row_version"] == 2

    # The car's own record now reads as owned by the new customer...
    assert client.get(f"/api/v1/assets/{aid}", headers=h).json()["customer_id"] == cid2
    # ...but the pre-existing order is untouched — still the original customer.
    order_after = client.get(f"/api/v1/orders/{order['id']}", headers=h).json()
    assert order_after["customer_id"] == cid1
    assert order_after["asset_id"] == aid

    # Ownership history: the old span is closed, a new open span exists —
    # nothing was rewritten in place (service-layer read, no API surface yet).
    from sqlalchemy import text as _text

    from business_os.shared_kernel.db import TenantContext, bind_tenant_scope, open_session
    from serviceflow.assets import service as assets_service

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        # users is RLS-exempt (identity bootstrap table) — safe to read
        # directly before any tenant scope is established. asset_ownership
        # is not: bind_tenant_scope() first, or RLS FORCE fail-closes it to
        # nothing regardless of the explicit scoped() filter below.
        user_id, company_id = db.execute(
            _text("SELECT id, company_id FROM users WHERE email = 'a@a.bg'"),
        ).one()
        bind_tenant_scope(db, company_id)
        ctx = TenantContext(company_id=company_id, user_id=user_id, is_owner=True)
        history = assets_service.list_ownership_history(db, ctx, uuid.UUID(aid))
        assert len(history) == 2
        open_rows = [h for h in history if h.ended_at is None]
        closed_rows = [h for h in history if h.ended_at is not None]
        assert len(open_rows) == 1
        assert len(closed_rows) == 1
        assert str(open_rows[0].customer_id) == cid2
        assert str(closed_rows[0].customer_id) == cid1


def test_transfer_owner_to_current_owner_is_idempotent(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    aid = _vehicle(client, h, cid, "WVWZZZ1JZ3W386752")

    r = client.post(f"/api/v1/assets/{aid}/transfer-owner", headers=h,
                    json={"customer_id": cid})
    assert r.status_code == 200
    # No-op: row_version must NOT have been bumped by a transfer to the
    # already-current owner (product spec step 2: idempotent, not an error).
    assert r.json()["row_version"] == 1


def test_transfer_owner_rejects_cross_tenant_customer(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    cid_a = _customer(client, h_a)
    aid = _vehicle(client, h_a, cid_a, "WVWZZZ1JZ3W386752")
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    cid_b = _customer(client, h_b)
    client.post("/api/v1/auth/logout", headers=h_b)

    # Back to company A: try to "transfer" the vehicle to a customer that
    # belongs to company B — must be rejected, not silently cross tenants.
    h_a2 = _login(client, "Сервиз А", "a@a.bg")
    r = client.post(f"/api/v1/assets/{aid}/transfer-owner", headers=h_a2,
                    json={"customer_id": cid_b})
    assert r.status_code == 404
    assert client.get(f"/api/v1/assets/{aid}", headers=h_a2).json()["customer_id"] == cid_a
