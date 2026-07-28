"""Company Provisioning Foundation (docs/business-os/18 §9 phase 2):
`ProvisionCompany` as the single atomic domain command, plus the read-only
vendor company list/detail routes.

Vendor auth/session mechanics (login, CSRF, cross-plane isolation, RLS/GUC
absence, correlation) are already covered by tests/test_vendor_security.py —
this file focuses on what is new: atomicity, the metadata-only read surface,
and the provisioning-specific behavior.
"""

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)

VENDOR = "/api/v1/platform-admin"
ADMIN_EMAIL = "vendor.admin@business-os.bg"
ADMIN_PASSWORD = "вендор-парола-123"
TENANT_EMAIL = "maria@a.bg"
TENANT_PASSWORD = "парола-123"


def _db() -> Iterator[object]:
    from business_os.shared_kernel.db import open_session

    return open_session(os.environ["SERVICEFLOW_DATABASE_URL"])


def _reset_rate_limiter() -> None:
    from business_os.platform_admin import service

    service._failures.clear()  # noqa: SLF001


def _seed_admin() -> uuid.UUID:
    from business_os.platform_admin.service import create_platform_admin

    for db in _db():
        admin, _ = create_platform_admin(db, "Вендор Админ", ADMIN_EMAIL, ADMIN_PASSWORD)
        return admin.id
    raise AssertionError("unreachable")


def _seed_tenant() -> None:
    from business_os.identity.service import seed_company

    for db in _db():
        seed_company(db, "Сервиз А", "Мария", TENANT_EMAIL, TENANT_PASSWORD, "1234")


def _vendor_login(client: TestClient) -> dict[str, object]:
    resp = client.post(f"{VENDOR}/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _tenant_login(client: TestClient) -> dict[str, object]:
    resp = client.post("/api/v1/auth/login",
                       json={"email": TENANT_EMAIL, "password": TENANT_PASSWORD})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _provision_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "company_name": "Нов Сервиз ЕООД",
        "owner_name": "Иван Иванов",
        "owner_email": "ivan@new-shop.bg",
        "owner_password": "нова-парола-1234",
    }
    payload.update(overrides)
    return payload


def _company_count() -> int:
    from business_os.identity.models import Company

    for db in _db():
        return len(list(db.scalars(select(Company))))  # type: ignore[attr-defined]
    raise AssertionError("unreachable")


def _audit_actions() -> list[str]:
    from business_os.platform_admin.models import PlatformAuditLog

    for db in _db():
        return list(db.scalars(  # type: ignore[attr-defined]
            select(PlatformAuditLog.action).order_by(PlatformAuditLog.created_at)))
    raise AssertionError("unreachable")


# --- The happy path: full atomic provisioning ---------------------------


def test_provision_company_creates_everything_atomically(client: TestClient) -> None:
    from business_os.identity.models import Company, User

    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.post(f"{VENDOR}/companies", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json=_provision_payload(business_profile="phone_repair",
                                               modules=["professional-services"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["business_profile"] == "phone_repair"
    assert body["activated_modules"] == ["professional-services"]
    assert body["subscription_state"] == "trial"
    assert body["trial_ends_at"]
    assert body["audit_id"]

    for db in _db():
        company = db.get(Company, uuid.UUID(body["company_id"]))  # type: ignore[attr-defined]
        assert company is not None
        assert company.subscription_state == "trial"
        assert company.trial_ends_at is not None
        assert company.settings["repairflow"]["business_profile"] == "phone_repair"
        assert company.settings["active_modules"] == ["professional-services"]

        owner = db.get(User, uuid.UUID(body["owner_id"]))  # type: ignore[attr-defined]
        assert owner is not None
        assert owner.company_id == company.id
        assert owner.is_owner is True
        assert owner.email == "ivan@new-shop.bg"

    assert _audit_actions().count("company.provisioned") == 1

    from business_os.platform_admin.models import PlatformAuditLog

    for db in _db():
        row = db.get(PlatformAuditLog, uuid.UUID(body["audit_id"]))  # type: ignore[attr-defined]
        assert row is not None
        assert row.action == "company.provisioned"
        assert row.company_id == uuid.UUID(body["company_id"])


def test_provision_company_defaults_to_generic_repair_profile(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.post(f"{VENDOR}/companies", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json=_provision_payload())
    assert resp.status_code == 200, resp.text
    assert resp.json()["business_profile"] == "generic_repair"
    assert resp.json()["activated_modules"] == []


def test_provision_company_rejects_an_invalid_business_profile(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.post(f"{VENDOR}/companies", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json=_provision_payload(business_profile="not_a_real_profile"))
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.provisioning.invalid_business_profile"
    assert _company_count() == 0


# --- Atomicity: the single most important property of this slice --------


def test_duplicate_owner_email_leaves_zero_trace(client: TestClient) -> None:
    """A forced failure partway through (owner_password is valid, but the
    email collides with an existing user) must leave no orphaned company, no
    orphaned audit row — nothing partially committed."""
    _reset_rate_limiter()
    _seed_admin()
    _seed_tenant()  # creates a user with TENANT_EMAIL
    me = _vendor_login(client)
    before = _company_count()
    before_audit = _audit_actions()

    resp = client.post(f"{VENDOR}/companies", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json=_provision_payload(owner_email=TENANT_EMAIL))
    assert resp.status_code == 409
    assert resp.json()["detail"]["message_key"] == "errors.provisioning.owner_email_taken"

    assert _company_count() == before  # the seed_tenant company, and nothing more
    assert _audit_actions() == before_audit  # no orphaned audit row either


def test_audit_write_failure_rolls_back_the_entire_provisioning_transaction(
    client: TestClient,
) -> None:
    """Provisioning is successful only if business data and the audit record
    commit together. Simulated here at the lowest level available — calling
    the service function directly with a platform_admin_id that does not
    exist triggers a foreign-key violation exactly when the audit row (the
    last write in the transaction) is flushed, forcing Postgres to roll back
    the whole transaction, company and owner included."""
    from sqlalchemy.exc import DatabaseError

    from business_os.identity.models import Company
    from business_os.platform_admin.service import provision_company

    before = _company_count()
    bogus_admin_id = uuid.uuid4()

    for db in _db():
        with pytest.raises(DatabaseError):
            provision_company(
                db, bogus_admin_id, "Ще Изчезне ЕООД", "Собственик", "will-vanish@shop.bg",
                "парола-1234567",
            )
        db.rollback()  # type: ignore[attr-defined]

    for db in _db():
        assert len(list(db.scalars(select(Company)))) == before  # type: ignore[attr-defined]
        assert db.scalar(  # type: ignore[attr-defined]
            select(Company).where(Company.name == "Ще Изчезне ЕООД")) is None


# --- Read-only company list/detail (metadata only) -----------------------


def test_company_list_and_detail_expose_only_documented_metadata(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)
    created = client.post(
        f"{VENDOR}/companies", headers={"X-CSRF-Token": str(me["csrf_token"])},
        json=_provision_payload(business_profile="automotive_repair",
                                modules=["professional-services"]),
    ).json()

    listing = client.get(f"{VENDOR}/companies")
    assert listing.status_code == 200
    rows = listing.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == created["company_id"]
    assert row["business_profile"] == "automotive_repair"
    assert row["active_modules"] == ["professional-services"]
    assert row["subscription_state"] == "trial"
    assert "trial_ends_at" in row
    assert "seat_limit" in row
    assert row["seat_usage"] == 1  # the first Owner ProvisionCompany just created
    # Never tenant operational data or PII beyond what's sanctioned.
    forbidden_keys = {"customers", "assets", "service_orders", "invoices", "password",
                      "password_hash", "owner_email", "requisites"}
    assert not forbidden_keys & row.keys()

    detail = client.get(f"{VENDOR}/companies/{created['company_id']}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["id"] == created["company_id"]
    assert "subscription_state_changed_at" in detail_body
    assert not forbidden_keys & detail_body.keys()


def test_vendor_seat_usage_reflects_real_tenant_employees(client: TestClient) -> None:
    """Closes the gap this file's own metadata test originally flagged
    (ADR-BOS-009 §Vendor data visibility lists seat usage as vendor-visible
    metadata) — added alongside Tenant Employee Management
    (docs/business-os/18 §9 phase 7), which is what finally gives
    `count_active_seats` something real to count."""
    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)
    created = client.post(
        f"{VENDOR}/companies", headers={"X-CSRF-Token": str(me["csrf_token"])},
        json=_provision_payload(owner_email="owner@grows.bg"),
    ).json()

    detail = client.get(f"{VENDOR}/companies/{created['company_id']}").json()
    assert detail["seat_usage"] == 1

    tenant_login = client.post("/api/v1/auth/login",
                               json={"email": "owner@grows.bg",
                                     "password": "нова-парола-1234"}).json()
    client.post("/api/v1/users", headers={"X-CSRF-Token": str(tenant_login["csrf_token"])},
               json={"name": "Служител", "email": "worker@grows.bg",
                     "password": "работник-парола-123"})

    detail = client.get(f"{VENDOR}/companies/{created['company_id']}").json()
    assert detail["seat_usage"] == 2


def test_company_detail_404s_for_a_nonexistent_id(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    _vendor_login(client)

    resp = client.get(f"{VENDOR}/companies/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.provisioning.company_not_found"


# --- Route boundary (regression of the existing vendor guard) -----------


def test_tenant_session_cannot_reach_any_provisioning_route(client: TestClient) -> None:
    _seed_tenant()
    me = _tenant_login(client)

    assert client.get(f"{VENDOR}/companies").status_code == 401
    assert client.get(f"{VENDOR}/companies/{uuid.uuid4()}").status_code == 401
    resp = client.post(f"{VENDOR}/companies", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json=_provision_payload())
    assert resp.status_code == 401
    assert _company_count() == 1  # only the seed_tenant company — nothing created


def test_unauthenticated_request_cannot_reach_any_provisioning_route(client: TestClient) -> None:
    assert client.get(f"{VENDOR}/companies").status_code == 401
    assert client.get(f"{VENDOR}/companies/{uuid.uuid4()}").status_code == 401
    assert client.post(f"{VENDOR}/companies", json=_provision_payload()).status_code == 401


def test_inactive_vendor_admin_cannot_provision(client: TestClient) -> None:
    from business_os.platform_admin.models import PlatformAdmin

    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)

    for db in _db():
        admin = db.scalar(select(PlatformAdmin))  # type: ignore[attr-defined]
        admin.is_active = False
        db.commit()  # type: ignore[attr-defined]

    resp = client.post(f"{VENDOR}/companies", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json=_provision_payload())
    assert resp.status_code == 401
    assert _company_count() == 0


def test_provision_company_requires_csrf(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    _vendor_login(client)

    resp = client.post(f"{VENDOR}/companies", json=_provision_payload())
    assert resp.status_code == 403
    assert _company_count() == 0


# --- Correlation regression ------------------------------------------------


def test_provisioning_audit_row_carries_a_request_id(client: TestClient) -> None:
    from business_os.platform_admin.models import PlatformAuditLog

    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)

    resp = client.post(f"{VENDOR}/companies", headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json=_provision_payload())
    request_id = resp.headers["X-Request-ID"]

    for db in _db():
        row = db.scalar(select(PlatformAuditLog)  # type: ignore[attr-defined]
                        .where(PlatformAuditLog.action == "company.provisioned"))
        assert row is not None
        assert str(row.request_id) == request_id


# --- Domain command discipline -------------------------------------------


def test_provision_company_is_the_only_public_write_entry_point_in_its_module() -> None:
    """docs/business-os/18 §9 phase 2 ("Provisioning as a Domain Command"):
    provision_company is the sole orchestration entry point. This does not
    forbid identity.contracts' smaller non-committing primitives (grant_module,
    set_business_profile, set_subscription_trial, provision_company) —
    those are provision_company's own building blocks, never meant to be
    composed independently by a second orchestrator — but no *second*
    provisioning-shaped function should appear in platform_admin.service."""
    import inspect

    from business_os.platform_admin import service

    candidates = {
        name for name, obj in vars(service).items()
        if inspect.isfunction(obj) and obj.__module__ == service.__name__
        and ("compan" in name or "provision" in name)  # "compan" covers company/companies
    }
    assert candidates == {"provision_company", "list_companies", "get_company"}, (
        f"unexpected company/provisioning-shaped functions in platform_admin.service: "
        f"{candidates} — company creation must only ever happen through provision_company"
    )