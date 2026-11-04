"""order-workflow-revamp WP-D (Q9/Q10): mileage is optional for every
business profile (reverses Cleanup batch Issue 26's automotive-required
rule). When given, it must not be lower than the asset's previously
recorded maximum unless the Owner explicitly confirms the reading — then
it is stored exactly as read, flagged `mileage_confirmed_lower`, with a
mandatory timeline comment (`mileage_override_confirmed` event).
Enforced server-side in serviceflow.service_orders.service.create()."""

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
    produce.

    order-workflow-revamp WP-C (Q18): flipping the settings flag alone no
    longer gets a company a usable asset type for that profile — each
    profile seeds exactly one type, and `seed_company` already seeded
    generic_repair's "other" before this call ever runs. Seed the target
    profile's type too (skipping if it already exists, for a test that
    calls this more than once)."""
    from sqlalchemy import select

    from business_os.identity import service as identity_service
    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.assets.models import AssetType
    from serviceflow.assets.service import BUSINESS_PROFILE_ASSET_TYPES, seed_default_types

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == email))
        assert owner is not None
        identity_service.set_business_profile(db, owner.company_id, profile)
        bind_tenant_scope(db, owner.company_id)
        target_code = BUSINESS_PROFILE_ASSET_TYPES[profile]["code"]
        already = db.scalar(select(AssetType).where(
            AssetType.company_id == owner.company_id, AssetType.code == target_code,
        ))
        if already is None:
            seed_default_types(db, owner.company_id, profile)
        db.commit()


def _customer_and_asset(client: TestClient, h: dict[str, str],
                        asset_type_code: str = "vehicle") -> tuple[str, str]:
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": "0888111222"}).json()["id"]
    if asset_type_code == "vehicle":
        field_values = {"brand": "BMW", "model": "3 Series"}
    elif asset_type_code == "other":
        field_values = {"description": "Самсунг телевизор"}
    else:
        field_values = {"brand": "Apple"}
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": asset_type_code, "field_values": field_values,
    }).json()["id"]
    return cid, aid


def _create_order(client: TestClient, h: dict[str, str], cid: str, aid: str,
                  mileage: int | None = None, mileage_confirmed_lower: bool = False,
                  mileage_override_comment: str | None = None,
                  complaint: str = "Странен шум") -> "object":
    body: dict[str, object] = {"customer_id": cid, "asset_id": aid, "complaint": complaint}
    if mileage is not None:
        body["mileage"] = mileage
    if mileage_confirmed_lower:
        body["mileage_confirmed_lower"] = True
    if mileage_override_comment is not None:
        body["mileage_override_comment"] = mileage_override_comment
    return client.post("/api/v1/orders", headers=h, json=body)


def _close_order(client: TestClient, h: dict[str, str], order_id: str) -> None:
    """Q6 means a second order against the same asset is blocked while the
    first is still open — tests that need multiple orders against one
    asset (to compare mileage across visits) must close the prior one
    first. "declined" is reachable directly from "received" (the status
    every freshly created order starts in)."""
    r = client.post(f"/api/v1/orders/{order_id}/status", headers=h,
                    json={"to": "declined", "reason": "Тест"})
    assert r.status_code == 200, r.text


def _login_as_worker(client: TestClient, owner_headers: dict[str, str],
                     email: str = "worker@a.bg") -> dict[str, str]:
    client.post("/api/v1/users", headers=owner_headers,
               json={"name": "Иво", "email": email, "password": "парола-за-иво-123"})
    client.post("/api/v1/auth/logout", headers=owner_headers)
    me = client.post("/api/v1/auth/login",
                     json={"email": email, "password": "парола-за-иво-123"}).json()
    return {"X-CSRF-Token": str(me["csrf_token"])}


# --- Q9: mileage is optional everywhere --------------------------------------


def test_mileage_optional_for_automotive_repair(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)

    resp = _create_order(client, h, cid, aid, mileage=None)
    assert resp.status_code == 201, resp.text
    assert resp.json()["mileage"] is None


def test_mileage_optional_for_generic_repair(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h, asset_type_code="other")

    resp = _create_order(client, h, cid, aid, mileage=None)
    assert resp.status_code == 201, resp.text
    assert resp.json()["mileage"] is None


def test_negative_mileage_rejected(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)

    resp = _create_order(client, h, cid, aid, mileage=-5)
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_mileage_accepted_for_any_asset_type_not_just_vehicle(client: TestClient) -> None:
    """Mirrors the old Issue 26 fact ("accepted for any asset type") — Q9
    just makes it optional everywhere too, doesn't narrow where it's
    accepted."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h, asset_type_code="other")

    resp = _create_order(client, h, cid, aid, mileage=100)
    assert resp.status_code == 201, resp.text
    assert resp.json()["mileage"] == 100


# --- Q9: must not go backwards, unless Q10-bypassed --------------------------


def test_mileage_equal_to_previous_max_is_accepted(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)
    first = _create_order(client, h, cid, aid, mileage=50_000)
    assert first.status_code == 201, first.text
    _close_order(client, h, first.json()["id"])

    second = _create_order(client, h, cid, aid, mileage=50_000)
    assert second.status_code == 201, second.text
    assert second.json()["mileage"] == 50_000
    assert second.json()["mileage_confirmed_lower"] is False


def test_mileage_higher_than_previous_max_is_accepted(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)
    first = _create_order(client, h, cid, aid, mileage=50_000)
    _close_order(client, h, first.json()["id"])

    second = _create_order(client, h, cid, aid, mileage=50_001)
    assert second.status_code == 201, second.text
    assert second.json()["mileage"] == 50_001


def test_mileage_lower_than_previous_rejected_without_bypass(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)
    first = _create_order(client, h, cid, aid, mileage=50_000)
    _close_order(client, h, first.json()["id"])

    second = _create_order(client, h, cid, aid, mileage=49_999)
    assert second.status_code == 409
    assert second.json()["detail"]["message_key"] == "errors.orders.mileage_lower_than_previous"
    assert second.json()["detail"]["params"]["previous"] == 50_000


def test_mileage_lower_than_previous_rejected_for_non_owner_even_with_bypass_fields(
    client: TestClient,
) -> None:
    """Q10: a non-Owner has no bypass at all — flat 403, not a 409 asking
    for confirmation. Setting the bypass fields anyway must not help."""
    h_owner = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h_owner)
    first = _create_order(client, h_owner, cid, aid, mileage=50_000)
    _close_order(client, h_owner, first.json()["id"])
    h_worker = _login_as_worker(client, h_owner)

    second = _create_order(
        client, h_worker, cid, aid, mileage=49_999,
        mileage_confirmed_lower=True, mileage_override_comment="По-малък пробег.",
    )
    assert second.status_code == 403
    assert second.json()["detail"]["message_key"] == "errors.auth.owner_required"


def test_mileage_lower_bypass_without_comment_rejected(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)
    first = _create_order(client, h, cid, aid, mileage=50_000)
    _close_order(client, h, first.json()["id"])

    second = _create_order(client, h, cid, aid, mileage=49_999, mileage_confirmed_lower=True)
    assert second.status_code == 400
    assert (second.json()["detail"]["message_key"]
            == "errors.orders.mileage_override_comment_required")


def test_owner_bypass_stores_actual_reading_flagged_and_timelined(client: TestClient) -> None:
    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)
    first = _create_order(client, h, cid, aid, mileage=50_000)
    _close_order(client, h, first.json()["id"])

    second = _create_order(
        client, h, cid, aid, mileage=49_000, mileage_confirmed_lower=True,
        mileage_override_comment="Клиентът смени таблото след ремонт на километража.",
    )
    assert second.status_code == 201, second.text
    body = second.json()
    # Stored exactly as read — never silently corrected to the previous max.
    assert body["mileage"] == 49_000
    assert body["mileage_confirmed_lower"] is True

    events = client.get(f"/api/v1/orders/{body['id']}/timeline", headers=h).json()
    override = next(e for e in events if e["event_type"] == "mileage_override_confirmed")
    assert override["data"]["reading"] == 49_000
    assert override["data"]["previous_max"] == 50_000
    assert override["data"]["comment"] == "Клиентът смени таблото след ремонт на километража."


def test_legacy_field_values_mileage_used_as_floor_when_no_order_has_one_yet(
    client: TestClient,
) -> None:
    """The floor also considers the legacy Asset.field_values["mileage"]
    (set directly here, simulating data from before order-level mileage
    existed) when no order has recorded one yet — same fallback
    GET .../service-history already uses for `current_mileage`."""
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.assets.models import Asset

    h = _login(client)
    _set_business_profile("a@a.bg", "automotive_repair")
    cid, aid = _customer_and_asset(client, h)

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        asset = db.get(Asset, aid)
        assert asset is not None
        asset.field_values = {**asset.field_values, "mileage": 80_000}
        db.commit()

    resp = _create_order(client, h, cid, aid, mileage=79_999)
    assert resp.status_code == 409
    assert resp.json()["detail"]["params"]["previous"] == 80_000


# --- Legacy rows --------------------------------------------------------------


def test_legacy_null_mileage_order_remains_readable(client: TestClient) -> None:
    """A pre-existing NULL-mileage row must still read back cleanly."""
    h = _login(client)
    cid, aid = _customer_and_asset(client, h, asset_type_code="other")
    created = _create_order(client, h, cid, aid, mileage=None)
    assert created.status_code == 201

    resp = client.get(f"/api/v1/orders/{created.json()['id']}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["mileage"] is None
    assert resp.json()["mileage_confirmed_lower"] is False
