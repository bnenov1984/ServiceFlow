"""FastAPI dependencies: DB session, authenticated tenant context, CSRF guard.

Error contract per docs/09 §1: message keys, never prose.

Business OS Identity public contract, part 1 of 2 (docs/business-os/16 —
Phase 3, mechanically enforced; supersedes the Phase 2 "Core contract v1"
docstring, which was documentation-only). Request-scoped, FastAPI
`Depends()`-wrapped surface — see `identity.contracts` for the plain
non-request-scoped counterpart. Verified exports (checked against actual
external call sites at Phase 3, not just documented — docs/business-os/16
§consumer matrix):

- `TenantDep` / `get_tenant` — the only constructor of tenant scope
  (ADR-016); yields a `TenantContext` (company_id, user_id, is_owner). See
  `shared_kernel.db` for `TenantContext` and the `scoped()` chokepoint.
  Used by every router in the codebase.
- `TenantDbDep` / `get_tenant_db` — a DB session with the RLS GUC already
  bound to the current tenant (ADR-016 layer 3). Same usage breadth.
- `require_csrf` — request guard for state-changing endpoints. Used by
  6 of 8 external routers.
- `require_owner` — request guard for owner-only endpoints. Used by
  `customers/router.py` today; narrower but real.
- `require_subscription_ok` — Core-owned mutation gate (ADR-BOS-012), sibling
  to each module's own `require_<module>_active` (ADR-BOS-010). Apply
  per-route, next to `require_csrf`, on mutating endpoints only — never at
  router level like `require_ps_active`, which also gates reads; a suspended
  company's data must stay fully readable (ADR-009's degradation philosophy).
  First consumer: `professional_services`'s own mutating routes.
- `AuthDep` / `get_auth` — the resolved (session, user) pair. **No external
  consumer exists today** (verified by Phase 3 discovery) — used only by
  `identity.router` itself. Kept available (a handler needing session/user
  fields `TenantContext` doesn't carry is a legitimate future need), but it
  is not part of the actively enforced Phase 3 boundary in the sense the
  other four are: nothing outside `identity` currently depends on it.

Everything else in `identity` (models, service, security, router) is
implementation detail — importing it directly from another module is what
the `identity-public-boundary` import-linter contract (backend/.importlinter)
mechanically blocks. The internal `identity.service` reference below is kept
as `_service` (leading underscore), not `service`: this closes the easy
`from business_os.identity.deps import service` re-export bypass (see
docs/business-os/16 for what this does and does not close).
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from business_os.identity import service as _service
from business_os.identity.models import AuthSession, User
from business_os.shared_kernel.db import TenantContext, bind_tenant_scope, open_session
from serviceflow.config import get_settings

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
    resolved = _service.resolve_session(db, raw)
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


def require_subscription_ok(tenant: TenantDep, db: DbDep) -> None:
    """Core-owned mutation gate (ADR-BOS-012): 402s a mutating request when
    the company's subscription is `grace_period`/`suspended`/`cancelled`.
    Never applied to reads or export/backup endpoints — those must keep
    working regardless of subscription standing (ADR-009's degradation
    philosophy, carried into ADR-018: "your data is always yours").

    Independent of module entitlement (`require_<module>_active`,
    ADR-BOS-010 §Decision 3): this checks subscription standing only, never
    `active_modules` — a suspended company keeps every entitlement it had,
    it just can't write anything until its standing improves.
    """
    company = _service.get_company(db, tenant.company_id)
    assert company is not None
    if company.subscription_state not in _service.MUTATION_ALLOWED_SUBSCRIPTION_STATES:
        raise _error(402, "subscription_not_active", "errors.subscription.mutations_blocked")


REPAIRFLOW_MODULE_KEY = "repairflow"


def require_repairflow_active(tenant: TenantDep, db: DbDep) -> None:
    """RepairFlow's own entitlement gate (ADR-BOS-010 §Decision 2), the same
    shape as `professional_services.deps.require_ps_active` — 404s the whole
    router, reads included, when the company isn't entitled. Lives here
    rather than in a dedicated RepairFlow package because RepairFlow has none
    (docs/business-os/18): it's split across 9 sibling `serviceflow.*`
    routers, every one of which already imports `TenantDep`/`DbDep` from this
    module. PO decision, 01.08.2026: no application is active by default —
    RepairFlow is a real, vendor-granted entitlement like any other module,
    not an implicit baseline."""
    if not _service.is_module_active(db, tenant.company_id, REPAIRFLOW_MODULE_KEY):
        raise _error(404, "module_inactive", "errors.repairflow.module_inactive")
