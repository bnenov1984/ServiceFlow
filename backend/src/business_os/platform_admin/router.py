"""Vendor Control Plane routes — `/api/v1/platform-admin/*` (ADR-BOS-009
§Console deployment shape).

Authenticate, identify yourself, log out; read-only company list/detail; the
atomic company-provisioning command. No entitlement *editing* UI beyond the
initial grant at provisioning, no subscription *transitions*, no seat-limit
enforcement, no tenant employee management — those remain later slices
(docs/business-os/18 §9 phases 3+) and must not be smuggled in here.

Every route here is a thin wrapper around `platform_admin.service` — no
provisioning logic lives in this file (docs/business-os/18 §9 phase 2,
"Provisioning as a Domain Command": `service.provision_company` is the only
supported orchestration entry point).

Error contract per docs/09 §1: message keys, never prose.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
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
    never tenant operational data, and no seat *usage* count in this slice
    (that needs a tenant employee count, out of scope, docs/business-os/18
    §9 phase 2)."""

    id: uuid.UUID
    name: str
    business_profile: str
    active_modules: list[str]
    subscription_state: str
    trial_ends_at: datetime | None
    seat_limit: int | None
    created_at: datetime


class CompanyDetail(CompanySummary):
    subscription_state_changed_at: datetime


def _to_summary(metadata: CompanyAdminMetadata) -> CompanySummary:
    return CompanySummary(
        id=metadata.id, name=metadata.name, business_profile=metadata.business_profile,
        active_modules=metadata.active_modules, subscription_state=metadata.subscription_state,
        trial_ends_at=metadata.trial_ends_at, seat_limit=metadata.seat_limit,
        created_at=metadata.created_at,
    )


@router.get("/companies")
def list_companies(auth: PlatformAdminDep, db: VendorDbDep) -> list[CompanySummary]:
    return [_to_summary(c) for c in service.list_companies(db)]


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
            body.owner_password, business_profile=body.business_profile, modules=body.modules,
        )
    except service.ProvisioningError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "provisioning_failed", "message_key": e.message_key, "params": {},
        }) from e
    return ProvisionCompanyResponse(
        company_id=result.company_id, owner_id=result.owner_id,
        subscription_state=result.subscription_state, trial_ends_at=result.trial_ends_at,
        business_profile=result.business_profile, activated_modules=result.activated_modules,
        audit_id=result.audit_id,
    )
