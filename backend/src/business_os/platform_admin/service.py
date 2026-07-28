"""Vendor Control Plane operations: login, session resolution, logout, bootstrap.

Every query against `platform_admins` / `platform_admin_sessions` lives here —
those tables are RLS-exempt (no `company_id` to scope by), so centralising the
queries is the compensating control, exactly as `identity.service` does for
`companies`/`users` (ADR-016 note).

This module never imports a tenant module, never constructs a `TenantContext`
and never calls `bind_tenant_scope`. A vendor session therefore leaves
`app.company_id` unset, and RLS's fail-closed policy returns zero rows for any
tenant table — the intended default (ADR-BOS-009 §Consequences).
"""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from business_os.identity import contracts as identity_contracts
from business_os.platform_admin import audit
from business_os.platform_admin.models import PlatformAdmin, PlatformAdminSession
from business_os.shared_kernel import correlation, passwords
from business_os.shared_kernel.events import DomainEvent, publish

# Shorter than the tenant session's 12h (identity.service.SESSION_TTL): a vendor
# credential spans every customer company, so an unattended browser is worth more
# to an attacker. Nothing else about the two session kinds is shared.
SESSION_TTL = timedelta(hours=4)
MAX_LOGIN_FAILURES = 5
LOCKOUT = timedelta(minutes=15)

# Diagnostic only, never an auth factor — bounded so a hostile client can't
# stuff an unbounded header into the database (same discipline as
# identity.router's device_label, just header-sourced instead of body-supplied).
MAX_USER_AGENT_LENGTH = 300

# `resolve_session` runs on every authenticated request; writing last_seen_at
# on every one of them would mean a DB round trip per GET. Update only when
# it's gone stale by more than this — plenty fresh for "is this session alive"
# review, and cuts write volume by roughly this factor under normal use.
LAST_SEEN_UPDATE_INTERVAL = timedelta(minutes=1)

# In-memory limiter, same trade-off identity makes: adequate for one process
# (ADR-006 topology), revisit when the app scales horizontally (ADR-017 trigger).
# Deliberately a separate dict from identity's — a tenant brute-force must never
# be able to lock out the vendor plane, or vice versa.
_failures: dict[str, list[datetime]] = defaultdict(list)


class VendorAuthError(Exception):
    def __init__(self, message_key: str, status: int = 401) -> None:
        self.message_key = message_key
        self.status = status


def _now() -> datetime:
    return datetime.now(UTC)


def normalize_email(value: str) -> str:
    """The login identifier is case- and whitespace-insensitive; the unique
    index (`lower(email)`) enforces that at the database too."""
    return value.strip().lower()


def _check_rate_limit(key: str) -> None:
    cutoff = _now() - LOCKOUT
    _failures[key] = [t for t in _failures[key] if t > cutoff]
    if len(_failures[key]) >= MAX_LOGIN_FAILURES:
        raise VendorAuthError("errors.auth.locked_out", status=429)


def find_by_email(db: Session, email: str) -> PlatformAdmin | None:
    return db.scalar(
        select(PlatformAdmin).where(func.lower(PlatformAdmin.email) == normalize_email(email))
    )


def _bounded_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    return user_agent[:MAX_USER_AGENT_LENGTH]


def login(db: Session, email: str, password: str, client_key: str,
          user_agent: str | None = None) -> tuple[PlatformAdminSession, str]:
    """Returns (session, raw_cookie_token). Raises VendorAuthError.

    Only ever looks in `platform_admins` — a tenant user's credentials cannot
    authenticate here, and this function is the sole entry point to the vendor
    plane. There is no combined login that searches both identity stores.

    `user_agent` is stored on the new session as diagnostic metadata only
    (bounded, see `_bounded_user_agent`) — never consulted for authentication.
    """
    key = f"platform-login:{client_key}:{normalize_email(email)}"
    _check_rate_limit(key)

    admin = find_by_email(db, email)
    if admin is None or not admin.is_active or not passwords.verify_secret(
        admin.password_hash, password
    ):
        _failures[key].append(_now())
        # An inactive or wrong-password admin is a real account we can attribute;
        # an unknown email is not, and inventing an actor for it would be a lie.
        # The submitted email is deliberately not recorded: an audit trail that
        # captures typo'd credentials eventually captures a password (11 §3).
        inactive = admin is not None and not admin.is_active
        audit.record(
            db, audit.ADMIN_LOGIN_FAILED, correlation.ensure_bound(),
            platform_admin_id=admin.id if admin is not None else None,
            detail={"reason": "inactive" if inactive else "invalid_credentials"},
        )
        db.commit()
        raise VendorAuthError("errors.auth.invalid_credentials")

    raw, token_hash = passwords.new_session_token()
    session = PlatformAdminSession(
        platform_admin_id=admin.id,
        token_hash=token_hash,
        csrf_token=passwords.new_csrf_token(),
        user_agent=_bounded_user_agent(user_agent),
        expires_at=_now() + SESSION_TTL,
    )
    db.add(session)
    audit.record(db, audit.ADMIN_LOGIN, correlation.ensure_bound(), platform_admin_id=admin.id)
    db.commit()
    return session, raw


def resolve_session(
    db: Session, raw_token: str
) -> tuple[PlatformAdminSession, PlatformAdmin] | None:
    """Resolve a vendor cookie. Returns None for anything not a live session of
    an active admin — including a tenant `sf_session` token, which simply is not
    in this table."""
    session = db.scalar(
        select(PlatformAdminSession).where(
            PlatformAdminSession.token_hash == passwords.hash_token(raw_token)
        )
    )
    if session is None or session.revoked_at is not None:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < _now():
        return None
    admin = db.get(PlatformAdmin, session.platform_admin_id)
    # Deactivating an admin kills their live sessions on the next request — no
    # separate revoke step to forget.
    if admin is None or not admin.is_active:
        return None

    last_seen_at = session.last_seen_at
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=UTC)
    if _now() - last_seen_at > LAST_SEEN_UPDATE_INTERVAL:
        session.last_seen_at = _now()
        db.commit()
    return session, admin


def logout(db: Session, session: PlatformAdminSession) -> None:
    session.revoked_at = _now()
    audit.record(db, audit.ADMIN_LOGOUT, correlation.ensure_bound(),
                 platform_admin_id=session.platform_admin_id)
    db.commit()


def create_platform_admin(db: Session, name: str, email: str, password: str
                          ) -> tuple[PlatformAdmin, bool]:
    """Returns (admin, created). Idempotent on the login identifier: an existing
    admin is returned untouched — never re-hashed, never reactivated, never
    renamed — so re-running the bootstrap can neither reset a live credential
    nor silently restore a deactivated one.

    There is no public registration path to this function: it is reachable only
    from the bootstrap CLI (`business_os.platform_admin.bootstrap`), never from
    an HTTP route.
    """
    existing = find_by_email(db, email)
    if existing is not None:
        return existing, False

    admin = PlatformAdmin(
        name=name,
        email=normalize_email(email),
        password_hash=passwords.hash_secret(password),
    )
    db.add(admin)
    db.flush()
    audit.record(db, audit.ADMIN_BOOTSTRAPPED, correlation.ensure_bound(),
                 platform_admin_id=admin.id, detail={"via": "bootstrap_cli"})
    db.commit()
    return admin, True


def get_admin(db: Session, admin_id: uuid.UUID) -> PlatformAdmin | None:
    return db.get(PlatformAdmin, admin_id)


# --- Company provisioning (docs/business-os/18 §9 phase 2) ------------------
#
# provision_company() is the ONLY entry point that may create a company.
# Future vendor features — wizard UI, CLI, import tools, reseller APIs,
# marketplace onboarding, automated signup — must all call it, never assemble
# their own create-company/create-owner/assign-modules sequence. No other
# function in this codebase may partially provision a company.

VALID_BUSINESS_PROFILES = frozenset({
    "automotive_repair", "phone_repair", "electronics_repair",
    "appliance_repair", "generic_repair",
})
DEFAULT_BUSINESS_PROFILE = "generic_repair"  # ADR-BOS-011 §Decision 2

TRIAL_DAYS = 14  # ADR-018's number, inherited unchanged by ADR-BOS-012


class ProvisioningError(Exception):
    def __init__(self, message_key: str, status: int = 409) -> None:
        self.message_key = message_key
        self.status = status


@dataclass(frozen=True)
class ProvisionResult:
    """The provisioning contract's own result shape — belongs to
    `provision_company` alone. A later slice (entitlement management,
    subscription transitions) must not bolt ad hoc fields onto this or grow
    a second, slightly-different result type; extend here if a genuine new
    provisioning-time fact needs surfacing, since this dataclass is the
    single definition every caller (the router, tests, any future non-HTTP
    caller) reads."""

    company_id: uuid.UUID
    owner_id: uuid.UUID
    subscription_state: str
    trial_ends_at: datetime
    business_profile: str
    activated_modules: list[str]
    audit_id: uuid.UUID


def provision_company(
    db: Session,
    platform_admin_id: uuid.UUID,
    company_name: str,
    owner_name: str,
    owner_email: str,
    owner_password: str,
    business_profile: str = DEFAULT_BUSINESS_PROFILE,
    modules: Sequence[str] = (),
) -> ProvisionResult:
    """The single atomic command that creates a new customer company: the
    company itself, its first Tenant Owner, the initial RepairFlow business
    profile, initial module entitlements, a subscription/licence baseline,
    and exactly one platform_audit_log row — all in one transaction.

    Every step below is non-committing (`identity.contracts.provision_company`
    /`grant_module`/`set_business_profile`/`set_subscription_trial`, plus this
    module's own `audit.record`); this function commits exactly once, at the
    very end, right after the audit row is added. A failure at *any* step —
    a duplicate owner email, an invalid business profile, or a failure
    writing the audit row itself — propagates before that commit is reached,
    so nothing here is ever partially persisted: company, owner, profile,
    entitlements, subscription baseline and the audit row land together or
    not at all. Provisioning is successful only if the business data and the
    audit record commit together — the audit row is part of the operation,
    not appended after it.

    Publishing `company_provisioned` (after the profile is assigned, so the
    event carries the profile the company was actually given) is how
    `serviceflow.assets` seeds this company's own RepairFlow asset types
    without platform_admin ever importing a ServiceFlow module — forbidden
    by `vendor-plane-not-tenant-code` — see that subscriber's own docstring
    (docs/business-os/18 §15).
    """
    if business_profile not in VALID_BUSINESS_PROFILES:
        raise ProvisioningError("errors.provisioning.invalid_business_profile", status=400)

    try:
        provisioned = identity_contracts.provision_company(
            db, company_name, owner_name, owner_email, owner_password
        )
    except identity_contracts.ProvisioningError as e:
        raise ProvisioningError(e.message_key, status=e.status) from e

    identity_contracts.set_business_profile(db, provisioned.company_id, business_profile)
    publish(db, DomainEvent(
        type="company_provisioned", company_id=provisioned.company_id,
        actor_user_id=None, data={"business_profile": business_profile},
    ))
    for module_key in modules:
        identity_contracts.grant_module(db, provisioned.company_id, module_key)
    trial_ends_at = identity_contracts.set_subscription_trial(
        db, provisioned.company_id, TRIAL_DAYS
    )

    audit_id = audit.record(
        db, audit.COMPANY_PROVISIONED, correlation.ensure_bound(),
        platform_admin_id=platform_admin_id,
        company_id=provisioned.company_id,
        detail={
            "business_profile": business_profile,
            "modules": list(modules),
            "subscription_state": "trial",
        },
    )
    db.commit()

    return ProvisionResult(
        company_id=provisioned.company_id,
        owner_id=provisioned.owner_id,
        subscription_state="trial",
        trial_ends_at=trial_ends_at,
        business_profile=business_profile,
        activated_modules=list(modules),
        audit_id=audit_id,
    )


def list_companies(db: Session) -> list[identity_contracts.CompanyAdminMetadata]:
    """Backs the vendor company-list route — metadata only (ADR-BOS-009
    §Vendor data visibility). A thin pass-through to identity.contracts, kept
    here (not called directly from the router) so every vendor route goes
    through this module the same way, regardless of which read/write it needs."""
    return identity_contracts.list_companies_admin_metadata(db)


def get_company(
    db: Session, company_id: uuid.UUID
) -> identity_contracts.CompanyAdminMetadata | None:
    """Backs the vendor company-detail route. `None` for a non-existent id —
    the router turns that into a 404, existence-checked server-side, never
    inferred from anything client-supplied (ADR-BOS-009 §Tenant isolation
    requirement, restated for the Control Plane)."""
    return identity_contracts.get_company_admin_metadata(db, company_id)


# --- Entitlement management (docs/business-os/18 §9 phase 3, ADR-BOS-010) --
#
# Entitlement mutation is exclusively a Vendor Control Plane action
# (ADR-BOS-010 §Decision 1) — never tenant-triggered, never a general
# company-settings PATCH (§Decision 5). Independent of subscription state
# (§Decision 3): neither function here reads or writes
# subscription_state/trial_ends_at/seat_limit — a suspended company's
# entitlements can still be changed, and changing an entitlement never
# touches subscription standing. The actual enforcement point remains
# `require_<module>_active` on each module's own router (e.g.
# professional_services.deps.require_ps_active), unchanged by this slice —
# granting/revoking here only flips the same `active_modules` flag that
# guard already reads.


class EntitlementError(Exception):
    def __init__(self, message_key: str, status: int = 409) -> None:
        self.message_key = message_key
        self.status = status


@dataclass(frozen=True)
class EntitlementResult:
    company_id: uuid.UUID
    module_key: str
    active_modules: list[str]
    changed: bool
    audit_id: uuid.UUID


def grant_entitlement(
    db: Session, platform_admin_id: uuid.UUID, company_id: uuid.UUID, module_key: str,
) -> EntitlementResult:
    """Grant one module entitlement to an existing company — its own atomic
    operation (existence check, mutation, one audit row, one commit): the
    audited-endpoint path ADR-BOS-010 §Decision 5 requires ("never a general
    company-settings PATCH"). Idempotent — granting an already-active module
    changes nothing (`changed=False`) but is still audited, since a vendor
    action attempted is itself worth a record even when it was a no-op.

    Validates nothing about `module_key` beyond non-emptiness (enforced by
    the router's `Path` constraint) — there is no module-key registry yet
    (ADR-BOS-010 §Alternatives: deferred until per-module trial/expiry is a
    real requirement), the same as `identity.service._activate_module`.
    """
    metadata = identity_contracts.get_company_admin_metadata(db, company_id)
    if metadata is None:
        raise EntitlementError("errors.provisioning.company_not_found", status=404)

    changed = module_key not in metadata.active_modules
    identity_contracts.grant_module(db, company_id, module_key)
    audit_id = audit.record(
        db, audit.MODULE_GRANTED, correlation.ensure_bound(),
        platform_admin_id=platform_admin_id, company_id=company_id,
        detail={"module_key": module_key, "changed": changed},
    )
    db.commit()

    updated = identity_contracts.get_company_admin_metadata(db, company_id)
    assert updated is not None
    return EntitlementResult(
        company_id=company_id, module_key=module_key,
        active_modules=updated.active_modules, changed=changed, audit_id=audit_id,
    )


def revoke_entitlement(
    db: Session, platform_admin_id: uuid.UUID, company_id: uuid.UUID, module_key: str,
) -> EntitlementResult:
    """Revoke one module entitlement — symmetric to `grant_entitlement` in
    every respect (existence check, one audit row, one commit, idempotent).
    Does not touch subscription state: a company can lose one module's
    entitlement while remaining fully paid up on everything else
    (ADR-BOS-010 §Decision 3)."""
    metadata = identity_contracts.get_company_admin_metadata(db, company_id)
    if metadata is None:
        raise EntitlementError("errors.provisioning.company_not_found", status=404)

    changed = module_key in metadata.active_modules
    identity_contracts.revoke_module(db, company_id, module_key)
    audit_id = audit.record(
        db, audit.MODULE_REVOKED, correlation.ensure_bound(),
        platform_admin_id=platform_admin_id, company_id=company_id,
        detail={"module_key": module_key, "changed": changed},
    )
    db.commit()

    updated = identity_contracts.get_company_admin_metadata(db, company_id)
    assert updated is not None
    return EntitlementResult(
        company_id=company_id, module_key=module_key,
        active_modules=updated.active_modules, changed=changed, audit_id=audit_id,
    )


# --- Subscription lifecycle (docs/business-os/18 §9 phase 4, ADR-BOS-012) --
#
# Transitions are Vendor-Administrator-only, always with a mandatory reason,
# recorded append-only — the same reasoned-change shape `PSDeadlineChange`
# established (ADR-BOS-012 §Decision), reused rather than invented. Unlike
# entitlement management, there is no "idempotent no-op" concept here: a
# transition is a real historical event, so `set_subscription_state` never
# checks whether `new_state` equals the current one — it just records what
# the vendor asserted, exactly as `change_deadline` never checks whether a
# new deadline equals the old one.
#
# Independent of entitlement (ADR-BOS-010 §Decision 3, restated from the
# other side): this never reads or writes `active_modules`. The actual
# mutation gate this feeds is `identity.deps.require_subscription_ok` —
# wired onto professional_services' own mutating routes in this slice
# (§12.4), not the whole application yet.


class SubscriptionError(Exception):
    def __init__(self, message_key: str, status: int = 409) -> None:
        self.message_key = message_key
        self.status = status


@dataclass(frozen=True)
class SubscriptionTransitionResult:
    company_id: uuid.UUID
    old_state: str
    new_state: str
    reason: str
    audit_id: uuid.UUID


def transition_subscription(
    db: Session, platform_admin_id: uuid.UUID, company_id: uuid.UUID,
    new_state: str, reason: str,
) -> SubscriptionTransitionResult:
    """Transition a company's subscription lifecycle state — its own atomic
    operation (validation, existence check, mutation, one audit row, one
    commit). `reason` is mandatory and free text (ADR-BOS-012 §Decision) —
    the first real use of `platform_audit_log.reason`, unused since it was
    added in migration 0012.
    """
    if new_state not in identity_contracts.SUBSCRIPTION_STATES:
        raise SubscriptionError("errors.subscription.invalid_state", status=400)
    stripped_reason = reason.strip()
    if not stripped_reason:
        raise SubscriptionError("errors.subscription.reason_required", status=400)

    metadata = identity_contracts.get_company_admin_metadata(db, company_id)
    if metadata is None:
        raise SubscriptionError("errors.provisioning.company_not_found", status=404)

    old_state = identity_contracts.set_subscription_state(db, company_id, new_state)
    audit_id = audit.record(
        db, audit.SUBSCRIPTION_TRANSITIONED, correlation.ensure_bound(),
        platform_admin_id=platform_admin_id, company_id=company_id,
        detail={"from": old_state, "to": new_state}, reason=stripped_reason,
    )
    db.commit()

    return SubscriptionTransitionResult(
        company_id=company_id, old_state=old_state, new_state=new_state,
        reason=stripped_reason, audit_id=audit_id,
    )
