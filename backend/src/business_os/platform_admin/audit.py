"""Platform audit log — the only write path, and the action vocabulary.

Append-only on three levels, deliberately redundant (ADR-BOS-009 §Audit logging):

1. this module exposes `record()` and nothing else — there is no update or
   delete function to call;
2. `backend/.importlinter` forbids every tenant module from importing this
   package at all, so tenant code cannot reach `record()` either;
3. a DB trigger rejects UPDATE/DELETE on the table regardless of role
   (migration 0012), the same role-independent guard `timeline_events` uses.

**Action naming.** `<subject>.<past_tense_verb>`, subject singular, lowercase,
dot-separated — declared as constants below so the vocabulary is greppable and
cannot drift into free-form strings scattered across handlers. Add a constant
here when a new vendor action ships; never inline a literal at the call site.

**Never** put a password, session token, CSRF token or any other secret in
`detail` — it is a plain JSONB column read by whoever reviews vendor activity.

**Correlation is mandatory, not optional.** `request_id` has no default —
`record()` cannot be called without one, so a row can never land with no way
to trace it back to the request or CLI run that wrote it. Callers get the
value from `business_os.shared_kernel.correlation.ensure_bound()`, which
reuses whatever the current request/CLI operation already bound rather than
each call site inventing its own.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from business_os.platform_admin.models import PlatformAuditLog
from business_os.shared_kernel.ids import new_id

# Authentication.
ADMIN_BOOTSTRAPPED = "platform_admin.bootstrapped"
ADMIN_LOGIN = "platform_admin.login"
ADMIN_LOGIN_FAILED = "platform_admin.login_failed"
ADMIN_LOGOUT = "platform_admin.logout"

# Company provisioning (docs/business-os/18 §9 phase 2).
COMPANY_PROVISIONED = "company.provisioned"

# Entitlement management (docs/business-os/18 §9 phase 3, ADR-BOS-010).
MODULE_GRANTED = "company.module_granted"
MODULE_REVOKED = "company.module_revoked"

# Every action this slice knows about. Kept as a frozenset so `record()` can
# reject a typo'd or ad-hoc action string at the call site rather than silently
# writing an unreviewable row (BOS-18 §9 phase 4 extends this list further).
KNOWN_ACTIONS = frozenset({
    ADMIN_BOOTSTRAPPED,
    ADMIN_LOGIN,
    ADMIN_LOGIN_FAILED,
    ADMIN_LOGOUT,
    COMPANY_PROVISIONED,
    MODULE_GRANTED,
    MODULE_REVOKED,
})


def record(
    db: Session,
    action: str,
    request_id: str,
    platform_admin_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
    reason: str | None = None,
) -> uuid.UUID:
    """Append one vendor audit row. Does not commit — the caller's transaction
    decides, so the audit row and the action it describes land together or not
    at all (same discipline as identity's `_audit`).

    `request_id` is a required parameter, not one that quietly defaults to
    `None` — see the module docstring. Pass
    `business_os.shared_kernel.correlation.ensure_bound()`, not a literal.

    Returns the new row's id, generated here (not left to the mapped column's
    default) so the caller has it immediately without an extra flush — e.g.
    `ProvisionCompany` hands it back as `ProvisionResult.audit_id`, a durable
    reference to the exact audit record this operation produced.
    """
    if action not in KNOWN_ACTIONS:
        raise ValueError(
            f"unknown platform audit action {action!r} — add a constant to "
            "business_os.platform_admin.audit rather than passing a literal"
        )
    audit_id = new_id()
    db.add(PlatformAuditLog(
        id=audit_id,
        platform_admin_id=platform_admin_id,
        company_id=company_id,
        action=action,
        detail=detail or {},
        reason=reason,
        request_id=uuid.UUID(request_id),
    ))
    return audit_id
