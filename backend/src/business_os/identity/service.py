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
from sqlalchemy.orm import Session

from business_os.identity import security
from business_os.identity.models import AuditLog, AuthSession, Company, User

logger = logging.getLogger(__name__)

SESSION_TTL = timedelta(hours=12)
MAX_LOGIN_FAILURES = 5
LOCKOUT = timedelta(minutes=15)
MAX_PIN_FAILURES = 5

# ADR-BOS-011 §Decision 2: identity only needs the fallback value for a
# company that predates the profile field (every seed_company-created
# company) — the full five-slug RepairFlow vocabulary and its validation
# belong to the Vendor Control Plane
# (business_os.platform_admin.service.VALID_BUSINESS_PROFILES), not to
# identity, which stores whatever string it is given.
DEFAULT_BUSINESS_PROFILE = "generic_repair"

# ADR-BOS-012: baseline for every vendor-provisioned company.
DEFAULT_SUBSCRIPTION_STATE = "trial"


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


def login(db: Session, email: str, password: str, device_label: str,
          client_key: str) -> tuple[AuthSession, str]:
    """Returns (session, raw_cookie_token). Raises AuthError."""
    _check_rate_limit(f"login:{client_key}:{email.lower()}", MAX_LOGIN_FAILURES)

    user = db.scalar(select(User).where(User.email.ilike(email)))
    if user is None or not user.is_active or not security.verify_secret(
        user.password_hash, password
    ):
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
    if user is None or not user.is_active:
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


def get_company(db: Session, company_id: uuid.UUID) -> Company | None:
    """Companies are RLS-exempt (ADR-016) — centralizing the lookup here is the
    documented compensating control; callers must not query Company directly."""
    return db.get(Company, company_id)


def list_companies(db: Session) -> list[Company]:
    """Companies are RLS-exempt (identity bootstrap) — centralized here, same
    discipline as `list_users`. Backs the Vendor Control Plane's company list
    (`identity.contracts.list_companies_admin_metadata`)."""
    return list(db.scalars(select(Company).order_by(Company.created_at)))


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


def set_subscription_trial(db: Session, company_id: uuid.UUID, trial_days: int) -> None:
    """Baseline subscription state for a freshly provisioned company
    (ADR-BOS-012: every vendor-created company starts in `trial`, full
    functionality, a fixed number of days). Non-committing — composed inside
    `ProvisionCompany`'s single transaction."""
    company = get_company(db, company_id)
    assert company is not None
    company.subscription_state = DEFAULT_SUBSCRIPTION_STATE
    company.subscription_state_changed_at = _now()
    company.trial_ends_at = _now() + timedelta(days=trial_days)


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


def seed_company(db: Session, company_name: str, owner_name: str, owner_email: str,
                 owner_password: str, owner_pin: str | None = None) -> Company:
    """Idempotent dev/staging seed: company + Owner (self-serve registration is Етап 3)."""
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
    _audit(db, company.id, None, "company_seeded", {"name": company_name})
    db.commit()
    return company
