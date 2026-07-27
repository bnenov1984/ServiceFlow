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
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from business_os.platform_admin import audit
from business_os.platform_admin.models import PlatformAdmin, PlatformAdminSession
from business_os.shared_kernel import correlation, passwords

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
