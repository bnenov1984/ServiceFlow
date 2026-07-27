"""Vendor Control Plane FastAPI dependencies — the route boundary itself.

`require_platform_admin` is the counterpart to `identity.deps.get_tenant`, and
the two can never satisfy each other (ADR-BOS-009, docs/11 §2):

- it reads **only** the vendor cookie (`sf_platform_session`), so presenting a
  tenant `sf_session` is indistinguishable from presenting nothing → 401;
- the vendor cookie is issued with `path=/api/v1/platform-admin`, so a browser
  never even transmits it to a tenant route;
- the two token stores are different tables, so neither token can resolve in the
  other plane's lookup even if a cookie is replayed by hand;
- nothing here constructs a `TenantContext` or calls `bind_tenant_scope`, so a
  vendor request leaves `app.company_id` unset and RLS denies every tenant row
  by default rather than by remembering to filter.

`get_db` is intentionally this package's own three lines rather than an import
of `identity.deps.get_db`: the vendor plane must not depend on the tenant
identity module, and `shared_kernel.db.open_session` is the neutral primitive
both planes are entitled to.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from business_os.platform_admin import service as _service
from business_os.platform_admin.models import PlatformAdmin, PlatformAdminSession
from business_os.shared_kernel.db import open_session
from serviceflow.config import get_settings

# Distinct from identity's `sf_session` — a different name for a different
# principal, so the two cookies coexist in one browser without either plane
# ever seeing the other's.
PLATFORM_SESSION_COOKIE = "sf_platform_session"
# Cookie path scoping: defence in depth, not the control itself (the control is
# that tenant routes never read this cookie name at all).
PLATFORM_COOKIE_PATH = "/api/v1/platform-admin"


def _error(status: int, code: str, message_key: str) -> HTTPException:
    return HTTPException(status_code=status, detail={
        "code": code, "message_key": message_key, "params": {},
    })


def get_db() -> Iterator[Session]:
    settings = get_settings()
    if settings.database_url is None:
        raise _error(503, "db_not_configured", "errors.db_not_configured")
    yield from open_session(settings.database_url)


VendorDbDep = Annotated[Session, Depends(get_db)]


def require_platform_admin(request: Request, db: VendorDbDep
                           ) -> tuple[PlatformAdminSession, PlatformAdmin]:
    """The vendor route guard. Satisfiable only by a live session of an active
    Vendor Administrator — an inactive one is rejected here, on every request,
    not only at login."""
    raw = request.cookies.get(PLATFORM_SESSION_COOKIE)
    if not raw:
        raise _error(401, "not_authenticated", "errors.auth.required")
    resolved = _service.resolve_session(db, raw)
    if resolved is None:
        raise _error(401, "session_invalid", "errors.auth.session_expired")
    return resolved


PlatformAdminDep = Annotated[
    tuple[PlatformAdminSession, PlatformAdmin], Depends(require_platform_admin)
]


def require_platform_csrf(request: Request, auth: PlatformAdminDep) -> None:
    """Apply to every state-changing vendor endpoint (docs/09 §1)."""
    session, _ = auth
    header = request.headers.get("X-CSRF-Token")
    if header is None or header != session.csrf_token:
        raise _error(403, "csrf_failed", "errors.auth.csrf")
