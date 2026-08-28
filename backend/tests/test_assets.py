"""Assets: seed types, field validation, identifier extraction + duplicates, isolation."""

import os
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
    from business_os.shared_kernel.db import open_session
    from serviceflow.assets.models import Asset

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
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

    # Verify via API: the old VIN's identifier row must have been replaced.
    r2 = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "Volkswagen", "model": "Golf", "vin": "WVWZZZ1JZ3W386752"},
    })
    assert r2.json()["duplicate_asset_ids"] == []  # old VIN row was replaced

    r3 = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "Audi", "model": "A4", "vin": "WAUZZZ8K9A123456"},
    })
    assert aid in r3.json()["duplicate_asset_ids"]


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
