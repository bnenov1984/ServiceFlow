"""Cleanup batch Issue 26: mileage is required at intake only for a company
whose own business_profile is "automotive_repair" — every other profile
keeps it fully optional, unchanged. Enforced server-side in
serviceflow.service_orders.service.create(), before order-number allocation."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _login(client: TestClient, company: str = "Автосервиз А",
          email: str = "a@a.bg") -> dict[str, str]:
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, company, "Owner", email, "парола-123")
    me = client.post("/api/v1/auth/login",
                     json={"email": email, "password": "парола-123"}).json()
    return {"X-CSRF-Token": str(me["csrf_token"])}


def _set_business_profile(email: str, profile: str) -> None:
    """Direct DB write — `seed_company` (the dev/CLI provisioning path every
    test in this repo's suite already uses) always tags a fresh company
    `generic_repair`; there is no HTTP endpoint that changes a company's own
    business_profile after provisioning (only the vendor provisioning flow
    sets it, once, at creation), so this mirrors this file's own tests'
    convention of reaching into the DB directly for state the API can't
    produce."""
    from sqlalchemy import select

    from business_os.identity import service as identity_service
    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == email))
        assert owner is not None
        identity_service.set_business_profile(db, owner.company_id, profile)
        db.commit()


def _customer_and_asset(client: TestClient, h: dict[str, str],
                        asset_type_code: str = "vehicle") -> tuple[str, str]:
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": "0888111222"}).json()["id"]
    field_values = (
        {"brand": "BMW", "model": "3 Series"} if asset_type_code == "vehicle"
        else {"brand": "Apple"}
    )
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": asset_type_code, "field_values": field_values,
    }).json()["id"]
    return cid, aid


def _create_order(client: TestClient, h: dict[str, str], cid: str, aid: str,
                  mileage: int | None) -> "object":
    body: dict[str, object] = {
        "customer_id": cid, "asset_id": aid, "complaint": "Странен шум",
    }
    if mileage is not None:
        body["mileage"] = mileage
    return client.post("/api/v1/orders", headers=h, json=body)


# --- Automotive: mileage required -------------------------------------------


def test_automotive_new_order_without_mileage_rejected(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)

    resp = _create_order(client, h, cid, aid, mileage=None)
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.orders.mileage_required"


def test_automotive_mileage_zero_accepted(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)

    resp = _create_order(client, h, cid, aid, mileage=0)
    assert resp.status_code == 201, resp.text
    assert resp.json()["mileage"] == 0


def test_automotive_positive_mileage_accepted(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)

    resp = _create_order(client, h, cid, aid, mileage=125_000)
    assert resp.status_code == 201, resp.text
    assert resp.json()["mileage"] == 125_000


def test_automotive_negative_mileage_rejected(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)

    resp = _create_order(client, h, cid, aid, mileage=-5)
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_automotive_missing_mileage_does_not_consume_an_order_number(client: TestClient) -> None:
    """The check runs before number allocation — a rejected request must
    never advance the per-company order sequence."""
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)

    rejected = _create_order(client, h, cid, aid, mileage=None)
    assert rejected.status_code == 400

    created = _create_order(client, h, cid, aid, mileage=1000)
    assert created.status_code == 201, created.text
    year = str(__import__("datetime").date.today().year)
    assert created.json()["number"] == f"{year}-00001"


# --- Non-automotive profiles: mileage stays optional ------------------------


def test_generic_repair_profile_order_creation_unaffected(client: TestClient) -> None:
    """Default seed_company profile is generic_repair — mileage stays fully
    optional, exactly as before this cleanup batch."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)

    resp = _create_order(client, h, cid, aid, mileage=None)
    assert resp.status_code == 201, resp.text
    assert resp.json()["mileage"] is None


def test_phone_repair_profile_order_creation_unaffected(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "phone_repair")
    cid, aid = _customer_and_asset(client, h)

    resp = _create_order(client, h, cid, aid, mileage=None)
    assert resp.status_code == 201, resp.text
    assert resp.json()["mileage"] is None


def test_automotive_company_non_vehicle_asset_still_requires_mileage(client: TestClient) -> None:
    """The gate is on the company's own business_profile (docs' own wording:
    "automotive_repair profile: mileage required for creation of a new
    order"), not on the specific asset type chosen for one order — matches
    the cleanup batch's explicit instruction to key this off the company
    profile, not a per-order asset-type check."""
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h, asset_type_code="phone")

    resp = _create_order(client, h, cid, aid, mileage=None)
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.orders.mileage_required"


# --- Legacy rows -------------------------------------------------------------


def test_legacy_null_mileage_order_remains_readable(client: TestClient) -> None:
    """A pre-existing NULL-mileage row (created before this batch, or for a
    non-automotive company) must still read back cleanly — no backfill, no
    migration, this batch never touches historical rows."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    created = _create_order(client, h, cid, aid, mileage=None)
    assert created.status_code == 201

    resp = client.get(f"/api/v1/orders/{created.json()['id']}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["mileage"] is None
