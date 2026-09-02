"""Identity operations: login, logout, PIN switch, session lookup.

All user/session queries live here (identity is the RLS-exempt tenant bootstrap;
centralizing queries is the compensating control — ADR-016).
"""

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from business_os.identity import security
from business_os.identity.models import AuditLog, AuthSession, Company, PasswordResetToken, User
from business_os.shared_kernel.events import DomainEvent, publish

logger = logging.getLogger(__name__)

SESSION_TTL = timedelta(hours=12)
MAX_LOGIN_FAILURES = 5
LOCKOUT = timedelta(minutes=15)
MAX_PIN_FAILURES = 5

# Tenant Forgot Password V1.
RESET_TOKEN_TTL = timedelta(minutes=30)
# Independent, conservative limits — reset-request abuse (bombing one
# inbox with reset emails, or one IP fishing across many addresses) is a
# different threat shape than login brute force, so its own keys/counts,
# not a reuse of MAX_LOGIN_FAILURES. Both share the existing LOCKOUT
# window (15 min) via `_check_rate_limit`.
MAX_RESET_REQUESTS_PER_EMAIL = 3
MAX_RESET_REQUESTS_PER_IP = 10
MAX_RESET_SUBMIT_ATTEMPTS_PER_IP = 10

# ADR-BOS-011 §Decision 2: identity only needs the fallback value for a
# company that predates the profile field (every seed_company-created
# company) — the full five-slug RepairFlow vocabulary and its validation
# belong to the Vendor Control Plane
# (business_os.platform_admin.service.VALID_BUSINESS_PROFILES), not to
# identity, which stores whatever string it is given.
DEFAULT_BUSINESS_PROFILE = "generic_repair"

# ADR-BOS-012: baseline for every vendor-provisioned company.
DEFAULT_SUBSCRIPTION_STATE = "trial"

# ADR-BOS-012 §Decision: the whole lifecycle. Unlike business_profile/
# module_key, identity DOES own this vocabulary — the enforcement point
# (require_subscription_ok, below) lives in this same module, and the ADR
# itself calls the state machine "Core-owned," not a vertical's concern.
SUBSCRIPTION_STATES = frozenset({"trial", "active", "grace_period", "suspended", "cancelled"})

# ADR-BOS-012 + ADR-009's degradation philosophy, carried into ADR-018 and
# restated here: only these two states permit tenant mutations. The other
# three (grace_period, suspended, cancelled) are read-only — all data
# visible, export/backup always available, mutations blocked with an
# explanation — never a full lockout. `require_subscription_ok` is the one
# enforcement point; nothing else in the codebase should re-derive this set.
MUTATION_ALLOWED_SUBSCRIPTION_STATES = frozenset({"trial", "active"})


class ProvisioningError(Exception):
    """Raised by `create_company_with_owner` on a state that must abort the
    whole provisioning transaction (docs/business-os/18 §9 phase 2) — never
    caught and silently worked around, only translated by
    `identity.contracts.provision_company` into the public error shape
    external callers see."""

    def __init__(self, message_key: str, status: int = 409) -> None:
        self.message_key = message_key
        self.status = status

# In-memory limiter: adequate for one process (ADR-006 topology); revisit when the
# app scales horizontally (ADR-017 trigger).
_failures: dict[str, list[datetime]] = defaultdict(list)


class AuthError(Exception):
    def __init__(self, message_key: str, status: int = 401) -> None:
        self.message_key = message_key
        self.status = status


def _now() -> datetime:
    return datetime.now(UTC)


def _check_rate_limit(key: str, max_failures: int) -> None:
    cutoff = _now() - LOCKOUT
    _failures[key] = [t for t in _failures[key] if t > cutoff]
    if len(_failures[key]) >= max_failures:
        raise AuthError("errors.auth.locked_out", status=429)


def _record_failure(key: str) -> None:
    _failures[key].append(_now())


def _audit(db: Session, company_id: uuid.UUID, user_id: uuid.UUID | None,
           action: str, detail: dict[str, Any] | None = None) -> None:
    db.add(AuditLog(company_id=company_id, user_id=user_id, action=action, detail=detail or {}))


def record_audit_event(db: Session, company_id: uuid.UUID, actor_user_id: uuid.UUID | None,
                       action: str, detail: dict[str, Any] | None = None) -> None:
    """Wave 5 Issue 17: the sanctioned way for another module (customer
    anonymization) to write a row to the same tenant `audit_log` company-
    settings/employee-management already use — thin pass-through to
    `_audit`, exposed here so `identity.contracts` can re-export it without
    reaching into the underscore-prefixed internal directly."""
    _audit(db, company_id, actor_user_id, action, detail)


def _is_company_archived(db: Session, company_id: uuid.UUID) -> bool:
    company = get_company(db, company_id)
    return company is not None and company.archived_at is not None


def login(db: Session, email: str, password: str, device_label: str,
          client_key: str) -> tuple[AuthSession, str]:
    """Returns (session, raw_cookie_token). Raises AuthError."""
    _check_rate_limit(f"login:{client_key}:{email.lower()}", MAX_LOGIN_FAILURES)

    user = db.scalar(select(User).where(User.email.ilike(email)))
    # An archived company's users fold into the same generic rejection as a
    # deactivated user or wrong password (never a distinct message) — same
    # anti-enumeration posture `not user.is_active` already has here.
    if user is None or not user.is_active or (
        user is not None and _is_company_archived(db, user.company_id)
    ) or not security.verify_secret(user.password_hash, password):
        _record_failure(f"login:{client_key}:{email.lower()}")
        if user is not None:
            _audit(db, user.company_id, user.id, "login_failed")
            db.commit()
        raise AuthError("errors.auth.invalid_credentials")

    raw, token_hash = security.new_session_token()
    session = AuthSession(
        company_id=user.company_id,
        login_user_id=user.id,
        user_id=user.id,
        token_hash=token_hash,
        csrf_token=security.new_csrf_token(),
        device_label=device_label[:100],
        expires_at=_now() + SESSION_TTL,
    )
    db.add(session)
    _audit(db, user.company_id, user.id, "login", {"device": device_label[:100]})
    db.commit()
    return session, raw


def resolve_session(db: Session, raw_token: str) -> tuple[AuthSession, User] | None:
    token_hash = security.hash_token(raw_token)
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
    if session is None or session.revoked_at is not None:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < _now():
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active or _is_company_archived(db, session.company_id):
        return None
    session.last_seen_at = _now()
    db.commit()
    return session, user


def logout(db: Session, session: AuthSession) -> None:
    session.revoked_at = _now()
    _audit(db, session.company_id, session.user_id, "logout")
    db.commit()


def pin_switch(db: Session, session: AuthSession, target_user_id: uuid.UUID,
               pin: str) -> User:
    """Swap the acting identity on an already-authenticated device (ADR-008)."""
    _check_rate_limit(f"pin:{session.id}", MAX_PIN_FAILURES)

    target = db.get(User, target_user_id)
    # Same-company check: identity bootstrap enforces tenancy by hand (ADR-016 note).
    if (
        target is None
        or target.company_id != session.company_id
        or not target.is_active
        or target.pin_hash is None
        or not security.verify_secret(target.pin_hash, pin)
    ):
        _record_failure(f"pin:{session.id}")
        _audit(db, session.company_id, session.user_id, "pin_switch_failed",
               {"target": str(target_user_id)})
        db.commit()
        raise AuthError("errors.auth.invalid_pin")

    session.user_id = target.id
    _audit(db, session.company_id, target.id, "pin_switch",
           {"from": str(session.login_user_id)})
    db.commit()
    return target


def set_own_pin(db: Session, user: User, pin: str) -> None:
    """Tenant self-service: any authenticated user may set or replace their
    own PIN (docs/business-os PIN self-service task) — the gap
    `create_employee`'s optional `pin` (an Owner setting one for someone
    *else* at creation time) never covered. No permission check beyond being
    authenticated as yourself: changing your own PIN needs no elevated
    privilege, and there is no `user_id` parameter anywhere in this path —
    structurally, this can only ever change the caller's own row. Same
    hashing as every other PIN write (`security.hash_secret`), so a PIN set
    here verifies through the existing `pin_switch` check unchanged."""
    user.pin_hash = security.hash_secret(pin)
    _audit(db, user.company_id, user.id, "pin_set")
    db.commit()


# --- Tenant Forgot Password V1 ----------------------------------------------
# Vendor/PlatformAdmin reset is explicitly out of scope — platform_admin has
# its own, permanently separate principal/session model (ADR-BOS-009) and is
# not touched by any of this.


def request_password_reset(db: Session, email: str, client_key: str) -> str | None:
    """Public, pre-auth (mirrors login()'s own shape — see identity/router.py's
    POST /auth/login: no CSRF, no subscription gate; the whole /auth/* surface
    is exempt from require_subscription_ok, enforced for every route under
    this prefix by test_identity_auth_mechanics_are_never_gated_by_
    subscription_state).

    Returns the raw reset token ONLY when a usable one was actually created
    — the caller (the router's delivery step) must never leak this back to
    the HTTP response. The public response is identical (generic success)
    whether or not this returns a token: unknown email, inactive user, and
    an archived company's user all fold into `None` here, the same
    anti-enumeration posture login() already established with its own
    single generic error.

    Rate-limited by TWO independent keys (IP and email), not one composite
    — a composite key alone would still let a single IP probe unlimited
    addresses (only the IP+specific-email pair would ever hit its own cap)
    or let unlimited IPs pile onto one address (the same gap the other way
    round). Both are checked, and this attempt recorded against both,
    before any DB work — never after."""
    ip_key = f"reset_request_ip:{client_key}"
    email_key = f"reset_request_email:{email.lower()}"
    _check_rate_limit(ip_key, MAX_RESET_REQUESTS_PER_IP)
    _check_rate_limit(email_key, MAX_RESET_REQUESTS_PER_EMAIL)
    _record_failure(ip_key)
    _record_failure(email_key)

    user = db.scalar(select(User).where(User.email.ilike(email)))
    if user is None or not user.is_active or _is_company_archived(db, user.company_id):
        return None

    # A fresh request invalidates every previous unused token for this user
    # — never more than one live token outstanding at a time.
    db.execute(
        sa_update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=_now())
    )

    raw, token_hash = security.new_session_token()
    db.add(PasswordResetToken(
        user_id=user.id, token_hash=token_hash, expires_at=_now() + RESET_TOKEN_TTL,
    ))
    # Never the raw token in the audit detail — the same discipline every
    # other sensitive-value audit call site in this codebase already follows.
    _audit(db, user.company_id, user.id, "password_reset_requested")
    db.commit()
    return raw


def reset_password(db: Session, raw_token: str, new_password: str, client_key: str) -> None:
    """Raises AuthError("errors.auth.reset_token_invalid") for every
    invalid/unknown/expired/already-used token, and for a token whose user
    is no longer active or whose company is now archived — deliberately one
    generic error in every case, never distinguishing why (same
    anti-enumeration reasoning request_password_reset's single `None`
    return already uses).

    Single-use, race-safe: locks the specific token row (`with_for_update`,
    the same pattern commercial.service.issue()/annul() already use for
    their own atomic single-transaction state transitions) before
    validating anything, so a second concurrent submission of the same raw
    token blocks until this one commits or rolls back, then sees it already
    consumed rather than racing it."""
    ip_key = f"reset_submit_ip:{client_key}"
    _check_rate_limit(ip_key, MAX_RESET_SUBMIT_ATTEMPTS_PER_IP)
    _record_failure(ip_key)

    token_hash = security.hash_token(raw_token)
    token = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )
    now = _now()
    expires_at = token.expires_at if token is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if token is None or token.used_at is not None or expires_at is None or expires_at < now:
        raise AuthError("errors.auth.reset_token_invalid", status=400)

    user = db.get(User, token.user_id)
    if user is None or not user.is_active or _is_company_archived(db, user.company_id):
        raise AuthError("errors.auth.reset_token_invalid", status=400)

    user.password_hash = security.hash_secret(new_password)
    # Consumes this token AND invalidates any other still-live one for the
    # same user in one statement — the current token already matches this
    # WHERE clause, since its own used_at is still NULL at this point.
    db.execute(
        sa_update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.execute(
        sa_update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    _audit(db, user.company_id, user.id, "password_reset_completed")
    db.commit()


def get_company(db: Session, company_id: uuid.UUID) -> Company | None:
    """Companies are RLS-exempt (ADR-016) — centralizing the lookup here is the
    documented compensating control; callers must not query Company directly."""
    return db.get(Company, company_id)


def list_companies(db: Session, status: str = "active") -> list[Company]:
    """Companies are RLS-exempt (identity bootstrap) — centralized here, same
    discipline as `list_users`. Backs the Vendor Control Plane's company list
    (`identity.contracts.list_companies_admin_metadata`).

    `status`: "active" (default, `archived_at IS NULL` — archived companies
    hidden by default), "archived" (`archived_at IS NOT NULL`), or "all" (no
    filter). The router constrains the query param to these three values;
    anything else is a caller bug, not a user-facing validation case."""
    stmt = select(Company).order_by(Company.created_at)
    if status == "active":
        stmt = stmt.where(Company.archived_at.is_(None))
    elif status == "archived":
        stmt = stmt.where(Company.archived_at.is_not(None))
    return list(db.scalars(stmt))


# --- Company legal requisites (invoice-readiness prerequisite slice;
# docs/ACCOUNTANT_REVIEW.md §4 R1/§2 T1) -------------------------------
#
# `companies.requisites` is schemaless JSONB and `companies.vat_registered`
# has no write path anywhere in the app today (audited: neither is ever set
# outside this module). The full legal field set an issued invoice will
# need is bounded by docs/ACCOUNTANT_REVIEW.md §3: name/address/ЕИК are
# LAW-CONFIRMED required (R1), the VAT number is derivable as "BG" + ЕИК
# once `vat_registered` is known (R2, no separate stored field needed), and
# МОЛ (R3) / IBAN (R4) are LAW-CONFIRMED not required — inventing beyond
# that list here would be exactly what that document exists to prevent.
# `address`, `phone`, and `eik` are therefore the only requisites keys this
# V1 slice exposes. Extending the set later is additive (new allow-listed
# keys), not a schema change.
COMPANY_REQUISITE_KEYS = ("address", "phone", "eik")


def update_company_requisites(
    db: Session, company_id: uuid.UUID, actor_user_id: uuid.UUID,
    fields: dict[str, Any],
) -> Company:
    """Owner-only (route-enforced). `fields` comes from the router's
    `CompanyRequisitesPatch` (Pydantic `extra="forbid"`, only `address`,
    `phone`, `vat_registered` declared) via `model_dump(exclude_unset=True)`
    — this function additionally filters to `COMPANY_REQUISITE_KEYS` before
    writing into the JSONB blob, so even a future caller passing a raw dict
    can never smuggle an arbitrary key into `requisites`. Reassigns the
    whole dict (never mutates in place) so SQLAlchemy's change tracking
    picks it up, matching `Customer.company_requisites = None` elsewhere."""
    company = get_company(db, company_id)
    assert company is not None

    requisite_updates = {k: v for k, v in fields.items() if k in COMPANY_REQUISITE_KEYS}
    if requisite_updates:
        company.requisites = {**company.requisites, **requisite_updates}
    if "vat_registered" in fields:
        company.vat_registered = fields["vat_registered"]

    audit_detail = dict(requisite_updates)
    if "vat_registered" in fields:
        audit_detail["vat_registered"] = fields["vat_registered"]
    _audit(db, company_id, actor_user_id, "company_requisites_updated", audit_detail)
    db.commit()
    return company


# --- RepairFlow warranty defaults (Wave 4 Issue 38) -------------------------
#
# Tenant/company configuration, Owner-editable — NOT Vendor provisioning data,
# unlike `settings.repairflow.business_profile` above (that one is set once at
# provisioning and never exposed for the tenant to edit). Stored inside the
# same `companies.settings` JSONB bag, same `repairflow.*` namespace
# `set_business_profile`/`_activate_module` already established — no new
# table, no schema change. `labor_days`/`parts_days` are independent optional
# integers: NULL/missing = no default configured, 0 = explicitly "Без
# гаранция", positive = days. Negative is rejected at the router (Pydantic
# `ge=0`), never reaches here.
WARRANTY_DEFAULT_KEYS = ("labor_days", "parts_days")


def get_warranty_defaults(db: Session, company_id: uuid.UUID) -> dict[str, int | None]:
    company = get_company(db, company_id)
    defaults = (company.settings.get("repairflow", {}).get("warranty_defaults", {})
               if company is not None else {})
    return {key: defaults.get(key) for key in WARRANTY_DEFAULT_KEYS}


def update_warranty_defaults(db: Session, company_id: uuid.UUID, actor_user_id: uuid.UUID,
                             fields: dict[str, Any]) -> Company:
    """Owner-only (route-enforced, `company_router`'s `require_owner`).
    `fields` comes from the router's `WarrantyDefaultsPatch`
    (`extra="forbid"`, only `labor_days`/`parts_days` declared) via
    `model_dump(exclude_unset=True)` — mirrors `update_company_requisites`'s
    allow-list discipline exactly, filtered to `WARRANTY_DEFAULT_KEYS` before
    writing. Reassigns every level of the JSONB path (never mutates in
    place), same reason `update_company_requisites`/`set_business_profile`
    both do: SQLAlchemy's change tracking only sees a replaced value."""
    company = get_company(db, company_id)
    assert company is not None

    updates = {k: v for k, v in fields.items() if k in WARRANTY_DEFAULT_KEYS}
    if updates:
        repairflow = {**company.settings.get("repairflow", {})}
        warranty_defaults = {**repairflow.get("warranty_defaults", {}), **updates}
        repairflow["warranty_defaults"] = warranty_defaults
        company.settings = {**company.settings, "repairflow": repairflow}
        _audit(db, company_id, actor_user_id, "warranty_defaults_updated", updates)
        db.commit()
    return company


def is_module_active(db: Session, company_id: uuid.UUID, module_key: str) -> bool:
    """Module activation (BOS-06), stored as `active_modules` inside the existing
    `companies.settings` JSONB — no dedicated table (BOS-02's Settings precedent:
    one flag, few modules, pilot scale — a registry table is deferred until that
    stops being true). Centralized here, same discipline as get_company: callers
    (routers, frontend via /me) must go through this function, never read
    `company.settings` directly."""
    company = get_company(db, company_id)
    if company is None:
        return False
    active: list[str] = company.settings.get("active_modules", [])
    return module_key in active


def active_modules(db: Session, company_id: uuid.UUID) -> list[str]:
    """The full list, for surfaces that need it (e.g. /me's nav-gating field)."""
    company = get_company(db, company_id)
    if company is None:
        return []
    result: list[str] = company.settings.get("active_modules", [])
    return result


def _activate_module(db: Session, company_id: uuid.UUID, module_key: str) -> None:
    """Idempotent, non-committing. Reassigns the settings dict (not an
    in-place mutation) so SQLAlchemy's change tracking picks it up without a
    MutableDict wrapper. Shared by `activate_module` (below, its own commit —
    the CLI/dev entry point) and `identity.contracts.grant_module` (no
    commit — composed inside `ProvisionCompany`'s single transaction,
    docs/business-os/18 §9 phase 2)."""
    company = get_company(db, company_id)
    assert company is not None
    current: list[str] = list(company.settings.get("active_modules", []))
    if module_key not in current:
        current.append(module_key)
        company.settings = {**company.settings, "active_modules": current}


def activate_module(db: Session, company_id: uuid.UUID, module_key: str) -> None:
    """Idempotent, standalone entry point (serviceflow/seed.py, tests) — commits.
    A caller that owns a larger transaction should use
    `identity.contracts.grant_module` instead."""
    _activate_module(db, company_id, module_key)
    db.commit()


def _deactivate_module(db: Session, company_id: uuid.UUID, module_key: str) -> None:
    """Idempotent, non-committing — symmetric to `_activate_module`. Revoking
    an entitlement is exclusively a Vendor Control Plane action
    (ADR-BOS-010 §Decision 1); the only caller today is
    `identity.contracts.revoke_module`, composed inside
    `platform_admin.service.revoke_entitlement`'s single-commit operation
    (docs/business-os/18 §9 phase 3). No standalone `deactivate_module`
    exists — nothing outside the Vendor Control Plane needs to revoke a
    module today, unlike `activate_module`'s CLI/dev seed use."""
    company = get_company(db, company_id)
    assert company is not None
    current: list[str] = list(company.settings.get("active_modules", []))
    if module_key in current:
        current.remove(module_key)
        company.settings = {**company.settings, "active_modules": current}


def set_business_profile(db: Session, company_id: uuid.UUID, profile: str) -> None:
    """Writes the RepairFlow business profile slug into
    `companies.settings.repairflow.business_profile` (ADR-BOS-011 §Decision 2)
    — same settings-JSONB-key pattern as `_activate_module`. Does not
    validate `profile`: that vocabulary belongs to the caller
    (`business_os.platform_admin.service.VALID_BUSINESS_PROFILES`), the same
    way `_activate_module` never validates `module_key`. Non-committing —
    composed inside `ProvisionCompany`'s single transaction."""
    company = get_company(db, company_id)
    assert company is not None
    repairflow = {**company.settings.get("repairflow", {}), "business_profile": profile}
    company.settings = {**company.settings, "repairflow": repairflow}


def get_business_profile(db: Session, company_id: uuid.UUID) -> str:
    company = get_company(db, company_id)
    if company is None:
        return DEFAULT_BUSINESS_PROFILE
    repairflow: dict[str, Any] = company.settings.get("repairflow", {})
    result: str = repairflow.get("business_profile", DEFAULT_BUSINESS_PROFILE)
    return result


def set_business_type_label(db: Session, company_id: uuid.UUID, label: str) -> None:
    """Writes the vendor-entered free-text business description into
    `companies.settings.repairflow.business_type_label` — same
    settings-JSONB-key pattern as `set_business_profile`, deliberately
    stored alongside it rather than on a dedicated column (no tenant route
    ever reads or writes `company.settings`, so this key is exactly as
    vendor-only as `business_profile` already is). Purely descriptive
    metadata: unlike `business_profile`, nothing anywhere may branch on this
    string's value (no validator, asset schema or workflow selection) — it
    exists only to be displayed back to the vendor. Non-committing —
    composed inside `ProvisionCompany`'s single transaction."""
    company = get_company(db, company_id)
    assert company is not None
    repairflow = {**company.settings.get("repairflow", {}), "business_type_label": label}
    company.settings = {**company.settings, "repairflow": repairflow}


def get_business_type_label(db: Session, company_id: uuid.UUID) -> str:
    """`""` if never assigned (e.g. a `seed_company`-created dev tenant,
    which — like `business_profile` — never sets this)."""
    company = get_company(db, company_id)
    if company is None:
        return ""
    repairflow: dict[str, Any] = company.settings.get("repairflow", {})
    result: str = repairflow.get("business_type_label", "")
    return result


def set_subscription_trial(db: Session, company_id: uuid.UUID, trial_days: int) -> datetime:
    """Baseline subscription state for a freshly provisioned company
    (ADR-BOS-012: every vendor-created company starts in `trial`, full
    functionality, a fixed number of days). Non-committing — composed inside
    `ProvisionCompany`'s single transaction.

    Returns the computed `trial_ends_at` so the caller (`ProvisionCompany`,
    via `identity.contracts`) can hand it back as `ProvisionResult.
    trial_ends_at` without re-deriving `_now() + timedelta(...)` a second
    time and risking the two computations drifting apart by a few
    microseconds."""
    company = get_company(db, company_id)
    assert company is not None
    company.subscription_state = DEFAULT_SUBSCRIPTION_STATE
    company.subscription_state_changed_at = _now()
    trial_ends_at = _now() + timedelta(days=trial_days)
    company.trial_ends_at = trial_ends_at
    return trial_ends_at


def set_subscription_state(db: Session, company_id: uuid.UUID, new_state: str) -> str:
    """A vendor-initiated subscription lifecycle transition (ADR-BOS-012) —
    non-committing, composed inside
    `platform_admin.service.transition_subscription`'s single transaction,
    the same reasoned-change discipline `PSDeadlineChange` established
    (mandatory reason, always recorded — validated by the caller, not here).

    Does not validate `new_state` against `SUBSCRIPTION_STATES` — that is
    the caller's job, mirroring `_activate_module` never validating
    `module_key` and `set_business_profile` never validating the RepairFlow
    vocabulary.

    Returns the *old* state, since the caller needs it for the audit
    record's `detail.from` — re-reading it after the assignment below would
    just return the new value.
    """
    company = get_company(db, company_id)
    assert company is not None
    old_state = company.subscription_state
    company.subscription_state = new_state
    company.subscription_state_changed_at = _now()
    return old_state


def set_seat_limit(db: Session, company_id: uuid.UUID, new_limit: int | None) -> int | None:
    """A vendor-initiated seat-limit change (docs/business-os/18 §9 phase 5)
    — non-committing, composed inside `platform_admin.service.set_seat_limit`'s
    single transaction. `None` means unlimited, the same nullable convention
    `companies.seat_limit` already had (BOS-18 §6.3's escape hatch). Does not
    validate `new_limit` beyond what the caller's Pydantic model already
    enforces — the same posture as `set_subscription_state` not validating
    `new_state`.

    Returns the *old* limit, since the caller needs it for the audit record's
    `detail.from`."""
    company = get_company(db, company_id)
    assert company is not None
    old_limit = company.seat_limit
    company.seat_limit = new_limit
    return old_limit


def archive_company(db: Session, company_id: uuid.UUID) -> datetime | None:
    """Logical/soft archive — sets `archived_at`, nothing else. No user,
    session, subscription, entitlement or business-data row is touched or
    deleted; login (`login`) and session resolution (`resolve_session`) both
    check `archived_at` directly, so an archived company's users are locked
    out and any already-live session stops authorising requests on its very
    next call, with no separate session-revocation step needed. Non-committing
    — composed inside `platform_admin.service.archive_company`'s single
    transaction. Returns the *old* `archived_at` (None if it wasn't archived),
    needed for the audit record's `detail`."""
    company = get_company(db, company_id)
    assert company is not None
    old = company.archived_at
    company.archived_at = _now()
    return old


def restore_company(db: Session, company_id: uuid.UUID) -> datetime | None:
    """Symmetric to `archive_company` — clears `archived_at`. Non-committing,
    composed inside `platform_admin.service.restore_company`'s single
    transaction. Returns the *old* `archived_at`."""
    company = get_company(db, company_id)
    assert company is not None
    old = company.archived_at
    company.archived_at = None
    return old


def create_company_with_owner(
    db: Session, company_name: str, owner_name: str, owner_email: str, owner_password: str,
) -> tuple[Company, User]:
    """Non-committing counterpart to `seed_company`, for `ProvisionCompany`
    (docs/business-os/18 §9 phase 2): the caller owns the single commit
    boundary for the whole provisioning operation, so this never commits.

    Unlike `seed_company` (an idempotent dev/CLI convenience that silently
    returns the existing company on a duplicate owner email), this **raises**
    `ProvisioningError` instead. `ProvisionCompany` is an audited vendor
    action recorded against the company it believes it just created — quietly
    handing back a different, pre-existing company would make that audit row
    describe something that didn't happen.
    """
    existing = db.scalar(select(User).where(User.email.ilike(owner_email)))
    if existing is not None:
        raise ProvisioningError("errors.provisioning.owner_email_taken")

    company = Company(name=company_name)
    db.add(company)
    db.flush()
    owner = User(
        company_id=company.id,
        name=owner_name,
        email=owner_email,
        password_hash=security.hash_secret(owner_password),
        is_owner=True,
    )
    db.add(owner)
    db.flush()
    return company, owner


def list_users(db: Session, company_id: uuid.UUID,
               include_inactive: bool = False) -> list[User]:
    """Users are RLS-exempt (identity bootstrap) — the company filter here IS the
    isolation, which is why this stays centralized (ADR-016 finding)."""
    stmt = select(User).where(User.company_id == company_id)
    if not include_inactive:
        stmt = stmt.where(User.is_active.is_(True))
    return list(db.scalars(stmt.order_by(User.name)))


def get_user_name(db: Session, company_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    """Wave 4 Issue 7: the one piece of user data another module needs
    (a technician's display name for the delivery-protocol snapshot) —
    company-scoped the same way every other identity lookup here is
    (users are RLS-exempt, so this IS the isolation). `None` for a user
    outside this company or a deactivated/deleted one, never a KeyError —
    a snapshot with a missing technician name degrades gracefully instead
    of failing delivery outright."""
    user = db.get(User, user_id)
    if user is None or user.company_id != company_id:
        return None
    return user.name


# --- Tenant employee management (docs/13 Étап 3, docs/business-os/18 §9
# phase 7) -------------------------------------------------------------
#
# Owner-only (enforced by identity.deps.require_owner at the route, same as
# every other admin action in docs/02 §12's permission matrix), bounded by
# the vendor-set seat limit (ADR-BOS-009 ownership matrix: Tenant Owner
# operates within the limit, never raises it). Every mutation writes one row
# to the existing tenant `audit_log` — the same table login/logout/pin_switch
# already use, via the same `_audit()` helper; no new table.


class EmployeeError(Exception):
    def __init__(self, message_key: str, status: int = 409) -> None:
        self.message_key = message_key
        self.status = status


def count_active_seats(db: Session, company_id: uuid.UUID) -> int:
    """Seats = active users, Owner and Worker alike (ADR-BOS-009: "a count of
    `users`, not the user list's business content"). A plain len() over
    `list_users` rather than a dedicated COUNT query — company sizes here are
    2-10 people (CLAUDE.md's own framing), so there is nothing to optimize."""
    return len(list_users(db, company_id, include_inactive=False))


def _count_active_owners_excluding(
    db: Session, company_id: uuid.UUID, exclude_user_id: uuid.UUID
) -> int:
    return sum(
        1 for u in list_users(db, company_id, include_inactive=False)
        if u.is_owner and u.id != exclude_user_id
    )


def create_employee(
    db: Session, company_id: uuid.UUID, actor_user_id: uuid.UUID,
    name: str, email: str, password: str, is_owner: bool = False, pin: str | None = None,
) -> User:
    """Tenant Owner creates a new employee. Raises `EmployeeError` on a
    duplicate global email (the same uniqueness `uq_users_email_lower`
    enforces at the database) or when the vendor-set seat limit is already
    reached — a `None` `seat_limit` means unlimited (BOS-18 §6.3's escape
    hatch), so that check is skipped entirely when there is no limit to
    check against."""
    existing = db.scalar(select(User).where(User.email.ilike(email)))
    if existing is not None:
        raise EmployeeError("errors.employees.email_taken", status=409)

    company = get_company(db, company_id)
    assert company is not None
    if company.seat_limit is not None and count_active_seats(db, company_id) >= company.seat_limit:
        raise EmployeeError("errors.employees.seat_limit_reached", status=409)

    employee = User(
        company_id=company_id, name=name, email=email,
        password_hash=security.hash_secret(password),
        pin_hash=security.hash_secret(pin) if pin else None,
        is_owner=is_owner,
    )
    db.add(employee)
    db.flush()
    _audit(db, company_id, actor_user_id, "employee_created",
           {"employee_id": str(employee.id), "is_owner": is_owner})
    db.commit()
    return employee


def update_employee(
    db: Session, company_id: uuid.UUID, actor_user_id: uuid.UUID, employee_id: uuid.UUID,
    is_active: bool | None = None, is_owner: bool | None = None,
) -> User:
    """Activate/deactivate an employee and/or change their role, in one
    call (a PATCH may touch either field, both, or neither). Two invariants,
    checked against the state this call would actually produce, not just the
    row's current value:

    - reactivating a previously-deactivated employee counts against the
      seat limit exactly like `create_employee` (a `None` limit means
      unlimited, same skip);
    - the last active Owner can never be deactivated or demoted — every
      company must keep at least one, checked by counting active owners
      *excluding this employee* so the employee's own current contribution
      doesn't mask the very thing being removed.

    Idempotent per field (setting a value to what it already is changes
    nothing) but always audited — a tenant admin action attempted is worth a
    record even when it turns out to be a no-op, the same discipline
    `platform_admin`'s entitlement grant/revoke already established.
    """
    employee = db.get(User, employee_id)
    if employee is None or employee.company_id != company_id:
        raise EmployeeError("errors.employees.not_found", status=404)

    was_active, was_owner = employee.is_active, employee.is_owner
    next_active = is_active if is_active is not None else was_active
    next_owner = is_owner if is_owner is not None else was_owner

    removing_owner_status = was_owner and not (next_active and next_owner)
    if removing_owner_status and _count_active_owners_excluding(
        db, company_id, employee_id
    ) == 0:
        raise EmployeeError("errors.employees.last_owner_protected", status=409)

    if next_active and not was_active:
        company = get_company(db, company_id)
        assert company is not None
        if (company.seat_limit is not None
                and count_active_seats(db, company_id) >= company.seat_limit):
            raise EmployeeError("errors.employees.seat_limit_reached", status=409)

    employee.is_active = next_active
    employee.is_owner = next_owner
    changed = (was_active, was_owner) != (next_active, next_owner)
    _audit(db, company_id, actor_user_id, "employee_updated", {
        "employee_id": str(employee_id), "changed": changed,
        "is_active": next_active, "is_owner": next_owner,
    })
    db.commit()
    return employee


def seed_company(db: Session, company_name: str, owner_name: str, owner_email: str,
                 owner_password: str, owner_pin: str | None = None) -> Company:
    """Idempotent dev/staging seed: company + Owner (self-serve registration is Етап 3).

    Publishes `company_provisioned` exactly like `ProvisionCompany` does —
    this is the only other code path that creates a company, and every
    company, seeded or vendor-provisioned, needs its own RepairFlow asset
    types (docs/business-os/18 §15). No `business_profile` is assigned by
    this dev/CLI path, so the event carries the same default
    `DEFAULT_BUSINESS_PROFILE` the identity-side reader falls back to.

    Grants `"repairflow"` unconditionally — unlike `ProvisionCompany` (the
    real vendor-facing path, which since the 01.08.2026 PO decision requires
    an explicit, non-empty module selection), this is a dev/staging
    convenience whose entire purpose is a working RepairFlow demo tenant;
    every existing caller (the CLI seed script, and every backend test's
    `_seed_tenant()` helper) already assumes RepairFlow just works after
    this call."""
    existing = db.scalar(select(User).where(User.email.ilike(owner_email)))
    if existing is not None:
        company = db.get(Company, existing.company_id)
        assert company is not None
        return company

    company = Company(name=company_name)
    db.add(company)
    db.flush()
    db.add(User(
        company_id=company.id,
        name=owner_name,
        email=owner_email,
        password_hash=security.hash_secret(owner_password),
        pin_hash=security.hash_secret(owner_pin) if owner_pin else None,
        is_owner=True,
    ))
    _activate_module(db, company.id, "repairflow")
    _audit(db, company.id, None, "company_seeded", {"name": company_name})
    publish(db, DomainEvent(
        type="company_provisioned", company_id=company.id, actor_user_id=None,
        data={"business_profile": DEFAULT_BUSINESS_PROFILE},
    ))
    db.commit()
    return company
