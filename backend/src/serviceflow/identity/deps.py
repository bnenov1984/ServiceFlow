"""FastAPI dependencies: DB session, authenticated tenant context, CSRF guard.

Error contract per docs/09 §1: message keys, never prose.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from serviceflow.config import get_settings
from serviceflow.identity import service
from serviceflow.identity.models import AuthSession, User
from serviceflow.shared_kernel.db import TenantContext, bind_tenant_scope, open_session

SESSION_COOKIE = "sf_session"


def _error(status: int, code: str, message_key: str) -> HTTPException:
    return HTTPException(status_code=status, detail={
        "code": code, "message_key": message_key, "params": {},
    })


def get_db() -> Iterator[Session]:
    settings = get_settings()
    if settings.database_url is None:
        raise _error(503, "db_not_configured", "errors.db_not_configured")
    yield from open_session(settings.database_url)


DbDep = Annotated[Session, Depends(get_db)]


def get_auth(request: Request, db: DbDep) -> tuple[AuthSession, User]:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise _error(401, "not_authenticated", "errors.auth.required")
    resolved = service.resolve_session(db, raw)
    if resolved is None:
        raise _error(401, "session_invalid", "errors.auth.session_expired")
    return resolved


AuthDep = Annotated[tuple[AuthSession, User], Depends(get_auth)]


def get_tenant(auth: AuthDep) -> TenantContext:
    """The only constructor of tenant scope (ADR-016)."""
    session, user = auth
    return TenantContext(company_id=session.company_id, user_id=user.id,
                         is_owner=user.is_owner)


TenantDep = Annotated[TenantContext, Depends(get_tenant)]


def get_tenant_db(db: DbDep, tenant: TenantDep) -> Session:
    """DB session with the RLS GUC bound to this tenant (ADR-016 layer 3).

    See shared_kernel.db module docstring: bind_tenant_scope() sets it on the
    current connection AND registers it to be reapplied on any later re-begin
    within this same request (mid-request commits included).
    """
    bind_tenant_scope(db, tenant.company_id)
    return db


TenantDbDep = Annotated[Session, Depends(get_tenant_db)]


def require_csrf(request: Request, auth: AuthDep) -> None:
    """Apply to every state-changing endpoint (docs/09 §1)."""
    session, _ = auth
    header = request.headers.get("X-CSRF-Token")
    if header is None or header != session.csrf_token:
        raise _error(403, "csrf_failed", "errors.auth.csrf")


def require_owner(auth: AuthDep) -> None:
    _, user = auth
    if not user.is_owner:
        raise _error(403, "owner_required", "errors.auth.owner_required")
