"""Auth endpoints per docs/09: login, logout, pin-switch, me."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from serviceflow.config import get_settings
from serviceflow.identity import service
from serviceflow.identity.deps import SESSION_COOKIE, AuthDep, DbDep, require_csrf
from serviceflow.identity.models import AuthSession, User

router = APIRouter()


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


class PinSwitchRequest(BaseModel):
    user_id: uuid.UUID
    pin: str = Field(min_length=1, max_length=20)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _me(session: AuthSession, user: User) -> MeResponse:
    return MeResponse(
        user_id=user.id, name=user.name, email=user.email, is_owner=user.is_owner,
        language=user.language, company_id=session.company_id,
        csrf_token=session.csrf_token,
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
    return _me(session, user)


@router.get("/me")
def me(auth: AuthDep) -> MeResponse:
    session, user = auth
    return _me(session, user)


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
    return _me(session, target)
