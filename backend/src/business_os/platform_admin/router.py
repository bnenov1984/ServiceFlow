"""Vendor Control Plane routes — `/api/v1/platform-admin/*` (ADR-BOS-009
§Console deployment shape).

Walking skeleton only: authenticate, identify yourself, log out. `GET /me`
exists to prove the boundary end to end, and returns the vendor admin's own
identity — no company list, no tenant data, no counts. Company browsing,
provisioning and entitlement mutation are the following slices
(docs/business-os/18 §9 phases 2-3) and must not be smuggled in here.

Error contract per docs/09 §1: message keys, never prose.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

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
            db, body.email, body.password, _client_key(request)
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
