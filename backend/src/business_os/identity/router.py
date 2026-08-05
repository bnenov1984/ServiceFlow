"""Auth endpoints per docs/09: login, logout, pin-switch, me.

users_router (`/api/v1/users`, not `/auth`) — Etap-2 shipped list-only (PIN
dialog, technician picker); create/activate/deactivate/role-change are Etap 3
(docs/13, docs/business-os/18 §9 phase 7): Owner-only, bounded by the
vendor-set seat limit (ADR-BOS-009 ownership matrix).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from business_os.identity import service
from business_os.identity.deps import (
    SESSION_COOKIE,
    AuthDep,
    DbDep,
    TenantDep,
    require_csrf,
    require_owner,
    require_subscription_ok,
)
from business_os.identity.models import AuthSession, User
from serviceflow.config import get_settings

router = APIRouter()
users_router = APIRouter()


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
        httponly=True, samesite="lax", secure=not get_settings().debug,
        max_age=int(service.SESSION_TTL.total_seconds()), path="/",
    )
    user = db.get(User, session.user_id)
    assert user is not None
    return _me(db, session, user)


@router.get("/me")
def me(auth: AuthDep, db: DbDep) -> MeResponse:
    session, user = auth
    return _me(db, session, user)


@router.post("/logout", dependencies=[Depends(require_csrf)])
def logout(auth: AuthDep, response: Response, db: DbDep) -> dict[str, bool]:
    session, _ = auth
    service.logout(db, session)
    response.delete_cookie(SESSION_COOKIE, path="/")
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
