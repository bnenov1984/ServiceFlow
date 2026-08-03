"""Identity tables per docs/08 §identity. Identity is the tenant bootstrap:
these tables are exempt from RLS (queries centralized here); RLS starts with the
first domain table (ADR-016 note)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id


class Company(Base, TimestampMixin):
    """`settings.repairflow.business_profile` (ADR-BOS-011 §Decision 2) and
    `settings.active_modules` (BOS-06) live inside the existing JSONB — the
    subscription columns below do not, because they are a small fixed set
    with their own types (BOS-18 §6.3), not an open-ended settings bag.

    `subscription_state` keeps a `server_default` permanently, not just for
    migration-day backfill: it also gives every company created outside
    `ProvisionCompany()` (`identity.service.seed_company`, the dev/CLI path)
    a sane value without that path needing to know about subscriptions at
    all. `ProvisionCompany()` always sets it explicitly to `'trial'`
    (ADR-BOS-012) regardless of the default.
    """

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    name: Mapped[str]
    requisites: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
    vat_registered: Mapped[bool] = mapped_column(default=False)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
    subscription_state: Mapped[str] = mapped_column(default="active", server_default="active")
    subscription_state_changed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    trial_ends_at: Mapped[datetime | None] = mapped_column(default=None)
    seat_limit: Mapped[int | None] = mapped_column(default=None)
    # Logical/soft archive (docs/business-os/18 §9 phase 6): `NULL` = active,
    # any timestamp = archived since then. The single source of truth — no
    # companion `is_archived` bool, same convention as `AuthSession.revoked_at`.
    archived_at: Mapped[datetime | None] = mapped_column(default=None)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        # Global (not per-company) uniqueness: email is the SaaS login identifier.
        Index("uq_users_email_lower", func.lower(text("email")), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str]
    email: Mapped[str]
    password_hash: Mapped[str]
    pin_hash: Mapped[str | None] = mapped_column(default=None)
    is_owner: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    language: Mapped[str] = mapped_column(default="bg", server_default="bg")


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    # Who authenticated the device vs who is currently acting (PIN switch, ADR-008).
    login_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(unique=True)
    csrf_token: Mapped[str]
    device_label: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)


class AuditLog(Base):
    """Technical audit (11 §2): logins, PIN switches, admin actions.
    Business history lives in the timeline, never here."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    action: Mapped[str]
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
