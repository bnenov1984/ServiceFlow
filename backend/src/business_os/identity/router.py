"""Auth endpoints per docs/09: login, logout, pin-switch, me.

users_router (GET /users) е отделен, защото живее на /api/v1/users, не /auth —
Етап-2 slice: list only (PIN dialog, technician picker); POST/PATCH/deactivate
са Етап 3 (администрация).
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
)
from business_os.identity.models import AuthSession, User
from serviceflow.config import get_settings

router = APIRouter()
users_router = APIRouter()


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    is_owner: bool
    is_active: bool


@users_router.get("")
def list_users(db: DbDep, tenant: TenantDep, include_inactive: bool = False) -> list[UserOut]:
    return [
        UserOut(id=u.id, name=u.name, is_owner=u.is_owner, is_active=u.is_active)
        for u in service.list_users(db, tenant.company_id, include_inactive)
    ]


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


class PinSwitchRequest(BaseModel):
    user_id: uuid.UUID
    pin: str = Field(min_length=1, max_length=20)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _me(db: Session, session: AuthSession, user: User) -> MeResponse:
    return MeResponse(
        user_id=user.id, name=user.name, email=user.email, is_owner=user.is_owner,
        language=user.language, company_id=session.company_id,
        csrf_token=session.csrf_token,
        active_modules=service.active_modules(db, session.company_id),
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
