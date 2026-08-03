"""Vendor Control Plane routes — `/api/v1/platform-admin/*` (ADR-BOS-009
§Console deployment shape).

Authenticate, identify yourself, log out; read-only company list/detail; the
atomic company-provisioning command; grant/revoke module entitlements;
subscription lifecycle transitions. No seat-limit enforcement, no tenant
employee management — those remain later slices (docs/business-os/18 §9
phase 5+) and must not be smuggled in here.

Every route here is a thin wrapper around `platform_admin.service` — no
provisioning, entitlement or subscription logic lives in this file
(docs/business-os/18 §9 phases 2-4: `service.provision_company`/
`grant_entitlement`/`revoke_entitlement`/`transition_subscription` are the
only supported orchestration entry points).

Error contract per docs/09 §1: message keys, never prose.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, EmailStr, Field

from business_os.identity.contracts import CompanyAdminMetadata
from business_os.platform_admin import service
from business_os.platform_admin.deps import (
    PLATFORM_COOKIE_PATH,
    PLATFORM_SESSION_COOKIE,
    PlatformAdminDep,
    VendorDbDep,
    require_platform_csrf,
)
from serviceflow.config import get_settings

router = APIRouter()


class VendorLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class PlatformAdminMe(BaseModel):
    """Deliberately narrow: who you are and the CSRF token you need. No
    `company_id` field exists here because a Vendor Administrator has no
    company — this response shape is where that stops being a comment and
    becomes a contract."""

    platform_admin_id: uuid.UUID
    name: str
    email: str
    csrf_token: str


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/auth/login")
def vendor_login(body: VendorLoginRequest, request: Request, response: Response,
                 db: VendorDbDep) -> PlatformAdminMe:
    try:
        session, raw_token = service.login(
            db, body.email, body.password, _client_key(request),
            user_agent=request.headers.get("user-agent"),
        )
    except service.VendorAuthError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "auth_failed", "message_key": e.message_key, "params": {},
        }) from e
    response.set_cookie(
        PLATFORM_SESSION_COOKIE, raw_token,
        httponly=True, samesite="lax", secure=not get_settings().debug,
        max_age=int(service.SESSION_TTL.total_seconds()), path=PLATFORM_COOKIE_PATH,
    )
    admin = service.get_admin(db, session.platform_admin_id)
    assert admin is not None
    return PlatformAdminMe(
        platform_admin_id=admin.id, name=admin.name, email=admin.email,
        csrf_token=session.csrf_token,
    )


@router.get("/me")
def vendor_me(auth: PlatformAdminDep) -> PlatformAdminMe:
    """The protected walking-skeleton read. Not audited: a GET of your own
    identity is not a state change, and auditing every read would bury the
    mutations the log exists for (ADR-BOS-009 audits *mutations*)."""
    session, admin = auth
    return PlatformAdminMe(
        platform_admin_id=admin.id, name=admin.name, email=admin.email,
        csrf_token=session.csrf_token,
    )


@router.post("/auth/logout", dependencies=[Depends(require_platform_csrf)])
def vendor_logout(auth: PlatformAdminDep, response: Response,
                  db: VendorDbDep) -> dict[str, bool]:
    session, _ = auth
    service.logout(db, session)
    response.delete_cookie(PLATFORM_SESSION_COOKIE, path=PLATFORM_COOKIE_PATH)
    return {"ok": True}


# --- Company list / detail (read-only, metadata per ADR-BOS-009) -----------


class CompanySummary(BaseModel):
    """Administrative metadata only (ADR-BOS-009 §Vendor data visibility) —
    never tenant operational data. `seat_usage` closes a gap flagged in the
    Company Provisioning slice: ADR-BOS-009 lists it as vendor-visible
    metadata alongside `seat_limit`, deferred only until Tenant Employee
    Management (docs/business-os/18 §9 phase 7) gave it something to count."""

    id: uuid.UUID
    name: str
    business_profile: str
    business_type_label: str
    active_modules: list[str]
    subscription_state: str
    trial_ends_at: datetime | None
    seat_limit: int | None
    seat_usage: int
    created_at: datetime
    archived_at: datetime | None


class CompanyDetail(CompanySummary):
    subscription_state_changed_at: datetime


def _to_summary(metadata: CompanyAdminMetadata) -> CompanySummary:
    return CompanySummary(
        id=metadata.id, name=metadata.name, business_profile=metadata.business_profile,
        business_type_label=metadata.business_type_label,
        active_modules=metadata.active_modules, subscription_state=metadata.subscription_state,
        trial_ends_at=metadata.trial_ends_at, seat_limit=metadata.seat_limit,
        seat_usage=metadata.seat_usage, created_at=metadata.created_at,
        archived_at=metadata.archived_at,
    )


@router.get("/companies")
def list_companies(
    auth: PlatformAdminDep, db: VendorDbDep,
    status: str = Query("active", pattern="^(active|archived|all)$"),
) -> list[CompanySummary]:
    """Archived companies are hidden by default (`status=active`); pass
    `status=archived` or `status=all` to see them."""
    return [_to_summary(c) for c in service.list_companies(db, status=status)]


@router.get("/companies/{company_id}")
def get_company(auth: PlatformAdminDep, db: VendorDbDep, company_id: uuid.UUID) -> CompanyDetail:
    metadata = service.get_company(db, company_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail={
            "code": "company_not_found", "message_key": "errors.provisioning.company_not_found",
            "params": {},
        })
    return CompanyDetail(
        **_to_summary(metadata).model_dump(),
        subscription_state_changed_at=metadata.subscription_state_changed_at,
    )


# --- Company provisioning ---------------------------------------------------


class ProvisionCompanyRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    owner_name: str = Field(min_length=1, max_length=200)
    owner_email: EmailStr
    owner_password: str = Field(min_length=12, max_length=200)
    business_profile: str = Field(default=service.DEFAULT_BUSINESS_PROFILE)
    business_type_label: str = Field(min_length=1, max_length=200)
    modules: list[str] = Field(default_factory=list)


class ProvisionCompanyResponse(BaseModel):
    """Mirrors `service.ProvisionResult` field-for-field — the HTTP shape of
    the provisioning contract, not a place to add response-only fields of
    its own."""

    company_id: uuid.UUID
    owner_id: uuid.UUID
    subscription_state: str
    trial_ends_at: datetime
    business_profile: str
    business_type_label: str
    activated_modules: list[str]
    audit_id: uuid.UUID


@router.post("/companies", dependencies=[Depends(require_platform_csrf)])
def provision_company(
    body: ProvisionCompanyRequest, auth: PlatformAdminDep, db: VendorDbDep,
) -> ProvisionCompanyResponse:
    """The only route that creates a company. See
    `service.provision_company`'s docstring for the atomicity guarantee this
    wraps unchanged."""
    _, admin = auth
    try:
        result = service.provision_company(
            db, admin.id, body.company_name, body.owner_name, body.owner_email,
            body.owner_password, business_profile=body.business_profile,
            business_type_label=body.business_type_label, modules=body.modules,
        )
    except service.ProvisioningError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "provisioning_failed", "message_key": e.message_key, "params": {},
        }) from e
    return ProvisionCompanyResponse(
        company_id=result.company_id, owner_id=result.owner_id,
        subscription_state=result.subscription_state, trial_ends_at=result.trial_ends_at,
        business_profile=result.business_profile, business_type_label=result.business_type_label,
        activated_modules=result.activated_modules, audit_id=result.audit_id,
    )


# --- Entitlement management (docs/business-os/18 §9 phase 3, ADR-BOS-010) --


class EntitlementResponse(BaseModel):
    """Mirrors `service.EntitlementResult` field-for-field. `active_modules`
    is the company's full set *after* this call — a vendor UI can render it
    directly without a second GET."""

    company_id: uuid.UUID
    module_key: str
    active_modules: list[str]
    changed: bool
    audit_id: uuid.UUID


def _to_entitlement_response(result: service.EntitlementResult) -> EntitlementResponse:
    return EntitlementResponse(
        company_id=result.company_id, module_key=result.module_key,
        active_modules=result.active_modules, changed=result.changed,
        audit_id=result.audit_id,
    )


@router.put("/companies/{company_id}/modules/{module_key}",
           dependencies=[Depends(require_platform_csrf)])
def grant_entitlement(
    auth: PlatformAdminDep, db: VendorDbDep, company_id: uuid.UUID,
    module_key: str = Path(min_length=1, max_length=50),
) -> EntitlementResponse:
    """Grant one module entitlement. Idempotent: calling this again on an
    already-active module is a harmless no-op (`changed=False` in the
    response), not an error."""
    _, admin = auth
    try:
        result = service.grant_entitlement(db, admin.id, company_id, module_key)
    except service.EntitlementError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "entitlement_failed", "message_key": e.message_key, "params": {},
        }) from e
    return _to_entitlement_response(result)


@router.delete("/companies/{company_id}/modules/{module_key}",
               dependencies=[Depends(require_platform_csrf)])
def revoke_entitlement(
    auth: PlatformAdminDep, db: VendorDbDep, company_id: uuid.UUID,
    module_key: str = Path(min_length=1, max_length=50),
) -> EntitlementResponse:
    """Revoke one module entitlement. Idempotent, symmetric to
    `grant_entitlement`. Never touches subscription state (ADR-BOS-010
    §Decision 3) — a company can lose one module while remaining fully paid
    up on everything else."""
    _, admin = auth
    try:
        result = service.revoke_entitlement(db, admin.id, company_id, module_key)
    except service.EntitlementError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "entitlement_failed", "message_key": e.message_key, "params": {},
        }) from e
    return _to_entitlement_response(result)


# --- Subscription lifecycle (docs/business-os/18 §9 phase 4, ADR-BOS-012) --


class SubscriptionTransitionRequest(BaseModel):
    new_state: str
    reason: str = Field(min_length=1, max_length=2000)


class SubscriptionTransitionResponse(BaseModel):
    """Mirrors `service.SubscriptionTransitionResult` field-for-field."""

    company_id: uuid.UUID
    old_state: str
    new_state: str
    reason: str
    audit_id: uuid.UUID


@router.post("/companies/{company_id}/subscription/transitions",
           dependencies=[Depends(require_platform_csrf)])
def transition_subscription(
    body: SubscriptionTransitionRequest, auth: PlatformAdminDep, db: VendorDbDep,
    company_id: uuid.UUID,
) -> SubscriptionTransitionResponse:
    """Transition a company's subscription lifecycle state (trial / active /
    grace_period / suspended / cancelled) — always with a mandatory reason.
    One endpoint, not one per state ("suspend", "reactivate", ...): the
    operation is the same reasoned-change shape regardless of direction, and
    the console's suspend/reactivate buttons are just this call with a
    different `new_state`."""
    _, admin = auth
    try:
        result = service.transition_subscription(
            db, admin.id, company_id, body.new_state, body.reason,
        )
    except service.SubscriptionError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "subscription_transition_failed", "message_key": e.message_key,
            "params": {},
        }) from e
    return SubscriptionTransitionResponse(
        company_id=result.company_id, old_state=result.old_state, new_state=result.new_state,
        reason=result.reason, audit_id=result.audit_id,
    )


# --- Seat limit (docs/business-os/18 §9 phase 5) ----------------------------


class SeatLimitRequest(BaseModel):
    seat_limit: int | None = Field(gt=0)


class SeatLimitResponse(BaseModel):
    """Mirrors `service.SeatLimitResult` field-for-field."""

    company_id: uuid.UUID
    seat_limit: int | None
    changed: bool
    audit_id: uuid.UUID


@router.put("/companies/{company_id}/seat-limit",
           dependencies=[Depends(require_platform_csrf)])
def set_seat_limit(
    body: SeatLimitRequest, auth: PlatformAdminDep, db: VendorDbDep, company_id: uuid.UUID,
) -> SeatLimitResponse:
    """Set a company's seat limit. `null` means unlimited. Idempotent in
    effect but always audited, even when the new value equals the current
    one (mirrors `grant_entitlement`/`revoke_entitlement`, not the
    reasoned-transition shape of subscription lifecycle changes — there is
    no mandatory reason here)."""
    _, admin = auth
    try:
        result = service.set_seat_limit(db, admin.id, company_id, body.seat_limit)
    except service.SeatLimitError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "seat_limit_failed", "message_key": e.message_key, "params": {},
        }) from e
    return SeatLimitResponse(
        company_id=result.company_id, seat_limit=result.seat_limit,
        changed=result.changed, audit_id=result.audit_id,
    )


# --- Company archiving (docs/business-os/18 §9 phase 6) --------------------


class ArchiveResponse(BaseModel):
    """Mirrors `service.ArchiveResult` field-for-field."""

    company_id: uuid.UUID
    archived_at: datetime | None
    changed: bool
    audit_id: uuid.UUID


@router.put("/companies/{company_id}/archive",
           dependencies=[Depends(require_platform_csrf)])
def archive_company(
    auth: PlatformAdminDep, db: VendorDbDep, company_id: uuid.UUID,
) -> ArchiveResponse:
    """Archive a company — a logical/soft archive, never a delete. No user,
    session, subscription, entitlement or business-data row is touched.
    Idempotent in effect but always audited, even when the company was
    already archived."""
    _, admin = auth
    try:
        result = service.archive_company(db, admin.id, company_id)
    except service.ArchiveError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "archive_failed", "message_key": e.message_key, "params": {},
        }) from e
    return ArchiveResponse(
        company_id=result.company_id, archived_at=result.archived_at,
        changed=result.changed, audit_id=result.audit_id,
    )


@router.put("/companies/{company_id}/restore",
           dependencies=[Depends(require_platform_csrf)])
def restore_company(
    auth: PlatformAdminDep, db: VendorDbDep, company_id: uuid.UUID,
) -> ArchiveResponse:
    """Restore an archived company. Idempotent, symmetric to
    `archive_company`."""
    _, admin = auth
    try:
        result = service.restore_company(db, admin.id, company_id)
    except service.ArchiveError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "archive_failed", "message_key": e.message_key, "params": {},
        }) from e
    return ArchiveResponse(
        company_id=result.company_id, archived_at=result.archived_at,
        changed=result.changed, audit_id=result.audit_id,
    )
