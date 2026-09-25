"""Auth endpoints per docs/09: login, logout, pin-switch, me.

users_router (`/api/v1/users`, not `/auth`) — Etap-2 shipped list-only (PIN
dialog, technician picker); create/activate/deactivate/role-change are Etap 3
(docs/13, docs/business-os/18 §9 phase 7): Owner-only, bounded by the
vendor-set seat limit (ADR-BOS-009 ownership matrix).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from business_os.identity import mail, service
from business_os.identity.deps import (
    SESSION_COOKIE,
    AuthDep,
    DbDep,
    TenantDep,
    require_csrf,
    require_owner,
    require_subscription_ok,
)
from business_os.identity.models import AuthSession, Company, User
from business_os.shared_kernel.cookies import session_cookie_policy
from business_os.shared_kernel.normalize import is_valid_eik, normalize_eik
from serviceflow.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()
users_router = APIRouter()
# Owner-only for both read and write (mirrors users_router / EmployeesPage's
# existing "no access" posture for non-owners, not just read-only) — company
# legal/accounting details are at least as sensitive as the employee list.
company_router = APIRouter(dependencies=[Depends(require_owner)])


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    is_owner: bool
    is_active: bool
    # Whether a PIN is set — never the hash itself. Lets PIN-switch UI (and
    # the idle-lock screen) tell "wrong PIN" apart from "no PIN set yet"
    # without ever exposing pin_hash.
    has_pin: bool


def _user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id, name=u.name, email=u.email, is_owner=u.is_owner, is_active=u.is_active,
        has_pin=u.pin_hash is not None,
    )


@users_router.get("")
def list_users(db: DbDep, tenant: TenantDep, include_inactive: bool = False) -> list[UserOut]:
    return [_user_out(u) for u in service.list_users(db, tenant.company_id, include_inactive)]


class EmployeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    is_owner: bool = False
    pin: str | None = Field(default=None, min_length=4, max_length=20)


class EmployeePatch(BaseModel):
    is_active: bool | None = None
    is_owner: bool | None = None


@users_router.post(
    "", dependencies=[Depends(require_csrf), Depends(require_owner),
                     Depends(require_subscription_ok)],
    status_code=201,
)
def create_employee(body: EmployeeIn, db: DbDep, tenant: TenantDep) -> UserOut:
    """Owner-only (docs/02 §12); bounded by the vendor-set seat limit
    (`errors.employees.seat_limit_reached` when there is no room, unless
    `seat_limit` is null — unlimited)."""
    try:
        employee = service.create_employee(
            db, tenant.company_id, tenant.user_id, body.name, body.email, body.password,
            is_owner=body.is_owner, pin=body.pin,
        )
    except service.EmployeeError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "employee_error", "message_key": e.message_key, "params": {},
        }) from e
    return _user_out(employee)


@users_router.patch(
    "/{user_id}", dependencies=[Depends(require_csrf), Depends(require_owner),
                                Depends(require_subscription_ok)],
)
def update_employee(user_id: uuid.UUID, body: EmployeePatch, db: DbDep,
                    tenant: TenantDep) -> UserOut:
    """Activate/deactivate and/or change role in one call. Reactivating
    counts against the seat limit like creation does; the last active Owner
    can never be deactivated or demoted (`errors.employees.
    last_owner_protected`)."""
    try:
        employee = service.update_employee(
            db, tenant.company_id, tenant.user_id, user_id,
            is_active=body.is_active, is_owner=body.is_owner,
        )
    except service.EmployeeError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "employee_error", "message_key": e.message_key, "params": {},
        }) from e
    return _user_out(employee)


class CompanyRequisitesPatch(BaseModel):
    # extra="forbid" is the allow-list enforcement point: only these four
    # fields can ever reach service.update_company_requisites — there is no
    # way to submit an arbitrary JSON key through this contract.
    model_config = ConfigDict(extra="forbid")

    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=30)
    # ЕИК/БУЛСТАТ (docs/ACCOUNTANT_REVIEW.md §3 R1, LAW-CONFIRMED required).
    # No separate VAT-number field: it's always "BG" + eik once
    # vat_registered is true (R2) — nothing to independently store.
    eik: str | None = Field(default=None, max_length=20)
    vat_registered: bool | None = None

    @field_validator("eik")
    @classmethod
    def _validate_eik(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_eik(value)
        if not normalized:
            return None
        if not is_valid_eik(normalized):
            raise ValueError("invalid EIK/BULSTAT: expected 9 or 13 digits")
        return normalized


class CompanyRequisitesOut(BaseModel):
    address: str | None
    phone: str | None
    eik: str | None
    vat_registered: bool


def _company_requisites_out(company: Company) -> CompanyRequisitesOut:
    requisites = company.requisites or {}
    return CompanyRequisitesOut(
        address=requisites.get("address"), phone=requisites.get("phone"),
        eik=requisites.get("eik"), vat_registered=company.vat_registered,
    )


@company_router.get("/requisites")
def get_company_requisites(db: DbDep, tenant: TenantDep) -> CompanyRequisitesOut:
    company = service.get_company(db, tenant.company_id)
    assert company is not None
    return _company_requisites_out(company)


@company_router.patch(
    "/requisites",
    dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
)
def update_company_requisites(
    body: CompanyRequisitesPatch, db: DbDep, tenant: TenantDep,
) -> CompanyRequisitesOut:
    fields = body.model_dump(exclude_unset=True)
    company = service.update_company_requisites(db, tenant.company_id, tenant.user_id, fields)
    return _company_requisites_out(company)


# --- RepairFlow warranty defaults (Wave 4 Issue 38) -------------------------

class WarrantyDefaultsPatch(BaseModel):
    # extra="forbid": same allow-list discipline as CompanyRequisitesPatch —
    # only these declared keys can ever reach service.update_warranty_defaults.
    model_config = ConfigDict(extra="forbid")

    labor_days: int | None = Field(default=None, ge=0)
    parts_days: int | None = Field(default=None, ge=0)
    # Audit correction (issue 04): free-text warranty terms ("гаранция на
    # сервиза") — set by Vendor/Admin at onboarding, edited afterward by the
    # Owner (this router's own require_owner gate covers post-onboarding
    # edits only; onboarding writes go through platform_admin, a separate
    # router entirely).
    standard_term: str | None = Field(default=None, max_length=200)
    conditions: str | None = Field(default=None, max_length=2000)
    text: str | None = Field(default=None, max_length=4000)
    additional_conditions: str | None = Field(default=None, max_length=2000)


class WarrantyDefaultsOut(BaseModel):
    labor_days: int | None
    parts_days: int | None
    standard_term: str | None
    conditions: str | None
    text: str | None
    additional_conditions: str | None


@company_router.get("/warranty-defaults")
def get_warranty_defaults(db: DbDep, tenant: TenantDep) -> WarrantyDefaultsOut:
    return WarrantyDefaultsOut(**service.get_warranty_defaults(db, tenant.company_id))


@company_router.patch(
    "/warranty-defaults",
    dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
)
def update_warranty_defaults(
    body: WarrantyDefaultsPatch, db: DbDep, tenant: TenantDep,
) -> WarrantyDefaultsOut:
    fields = body.model_dump(exclude_unset=True)
    service.update_warranty_defaults(db, tenant.company_id, tenant.user_id, fields)
    return WarrantyDefaultsOut(**service.get_warranty_defaults(db, tenant.company_id))


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    device_label: str = Field(default="", max_length=100)


class MeResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    is_owner: bool
    language: str
    company_id: uuid.UUID
    csrf_token: str
    active_modules: list[str]
    seat_limit: int | None
    seat_usage: int
    has_pin: bool
    # Wave 4 Issue 38: exposed to every authenticated user (not owner-gated,
    # unlike /company/warranty-defaults' PATCH) — any technician opening the
    # delivery dialog or adding a part needs these to prefill, the same
    # reason `active_modules` already rides on /me rather than a dedicated
    # per-page fetch.
    warranty_defaults: WarrantyDefaultsOut
    # Cleanup batch Issue 26: any authenticated user creating an order needs
    # this to know whether intake must require mileage (the backend is
    # still the actual enforcement — see service_orders.service.create() —
    # this only lets the frontend mark the field required/show the right
    # copy before submitting, same "prefill/UX hint, not the authority"
    # role warranty_defaults already plays above).
    business_profile: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=500)
    # Same bound as EmployeeIn.password above — one password-policy
    # vocabulary, not two.
    password: str = Field(min_length=12, max_length=200)


class PinSwitchRequest(BaseModel):
    user_id: uuid.UUID
    pin: str = Field(min_length=1, max_length=20)


class SetPinRequest(BaseModel):
    # Same bounds as EmployeeIn.pin (an Owner setting one for someone else at
    # creation time) — one PIN vocabulary, not two.
    pin: str = Field(min_length=4, max_length=20)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _me(db: Session, session: AuthSession, user: User) -> MeResponse:
    company = service.get_company(db, session.company_id)
    assert company is not None
    return MeResponse(
        user_id=user.id, name=user.name, email=user.email, is_owner=user.is_owner,
        language=user.language, company_id=session.company_id,
        csrf_token=session.csrf_token,
        active_modules=service.active_modules(db, session.company_id),
        seat_limit=company.seat_limit,
        seat_usage=service.count_active_seats(db, session.company_id),
        has_pin=user.pin_hash is not None,
        warranty_defaults=WarrantyDefaultsOut(
            **service.get_warranty_defaults(db, session.company_id)
        ),
        business_profile=service.get_business_profile(db, session.company_id),
    )


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, db: DbDep) -> MeResponse:
    try:
        session, raw_token = service.login(
            db, body.email, body.password, body.device_label, _client_key(request)
        )
    except service.AuthError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "auth_failed", "message_key": e.message_key, "params": {},
        }) from e
    response.set_cookie(
        SESSION_COOKIE, raw_token,
        httponly=True, max_age=int(service.SESSION_TTL.total_seconds()), path="/",
        **session_cookie_policy(debug=get_settings().debug),
    )
    user = db.get(User, session.user_id)
    assert user is not None
    return _me(db, session, user)


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, request: Request, db: DbDep) -> dict[str, bool]:
    """Tenant Forgot Password V1. Public, pre-auth — no CSRF (mirrors
    `/auth/login`, which has none either: there is no session yet to bind
    one to), no subscription gate (the whole `/auth/*` surface is exempt,
    `test_identity_auth_mechanics_are_never_gated_by_subscription_state`
    enforces this for every route under this prefix — a suspended company's
    user must still be able to get back in).

    Always returns the same generic-success shape regardless of whether the
    email exists, belongs to an active user, or belongs to an archived
    company, and regardless of whether the delivery attempt below actually
    succeeds — see `identity.service.request_password_reset()`'s own
    docstring for the anti-enumeration reasoning; a mail-provider outage
    must never turn into a distinguishable response either. The raw token
    is never returned to the caller — it is either handed to
    `identity.mail.send_password_reset_email` (real delivery) or, only
    under `settings.debug`, logged server-side for local testing; in
    production (`debug=False`) it is never logged anywhere."""
    try:
        raw_token = service.request_password_reset(db, body.email, _client_key(request))
    except service.AuthError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "auth_failed", "message_key": e.message_key, "params": {},
        }) from e

    if raw_token is not None:
        settings = get_settings()
        if settings.debug:
            logger.info(
                "forgot_password (debug): reset link = %s",
                mail.build_reset_link(raw_token),
            )
        mail.send_password_reset_email(body.email, raw_token)
    return {"ok": True}


@router.post("/reset-password")
def reset_password_endpoint(
    body: ResetPasswordRequest, request: Request, db: DbDep,
) -> dict[str, bool]:
    """Same public, pre-auth posture as `forgot_password` above. Deliberately
    does not log the caller in / set a session cookie afterward: every
    existing session for this user was just revoked
    (`identity.service.reset_password()`), so auto-login here would
    immediately create a brand new one while the caller has only proven
    possession of the reset link, not re-entered their (new) password at a
    real login prompt."""
    try:
        service.reset_password(db, body.token, body.password, _client_key(request))
    except service.AuthError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "auth_failed", "message_key": e.message_key, "params": {},
        }) from e
    return {"ok": True}


@router.get("/me")
def me(auth: AuthDep, db: DbDep) -> MeResponse:
    session, user = auth
    return _me(db, session, user)


@router.post("/logout", dependencies=[Depends(require_csrf)])
def logout(auth: AuthDep, response: Response, db: DbDep) -> dict[str, bool]:
    session, _ = auth
    service.logout(db, session)
    response.delete_cookie(
        SESSION_COOKIE, path="/", **session_cookie_policy(debug=get_settings().debug)
    )
    return {"ok": True}


@router.post("/pin-switch", dependencies=[Depends(require_csrf)])
def pin_switch(body: PinSwitchRequest, auth: AuthDep, db: DbDep) -> MeResponse:
    session, _ = auth
    try:
        target = service.pin_switch(db, session, body.user_id, body.pin)
    except service.AuthError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "pin_failed", "message_key": e.message_key, "params": {},
        }) from e
    return _me(db, session, target)


@router.post("/pin", dependencies=[Depends(require_csrf)])
def set_pin(body: SetPinRequest, auth: AuthDep, db: DbDep) -> MeResponse:
    """Tenant self-service: set or replace the caller's own PIN. No
    `user_id` in the request — there is nothing here a caller could point
    at someone else's account. Never touched by Vendor provisioning
    (`ProvisionCompanyRequest` has no PIN field, and never will).

    Not gated by `require_subscription_ok`: the whole `/auth/*` surface is
    identity/session mechanics exempt from the mutation gate (same as
    `logout`/`pin-switch`, enforced by
    `test_identity_auth_mechanics_are_never_gated_by_subscription_state`) —
    a suspended company's owner must still be able to set a PIN and get
    into the app to see why (ADR-009's "all data visible" even suspended),
    the same reasoning that already keeps login/logout/pin-switch open."""
    session, user = auth
    service.set_own_pin(db, user, body.pin)
    return _me(db, session, user)
