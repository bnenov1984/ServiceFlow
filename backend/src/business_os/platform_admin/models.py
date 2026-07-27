"""Vendor Control Plane tables (ADR-BOS-009, docs/business-os/18 §6.1/§6.2).

None of these carry `company_id` — a Vendor Administrator is not scoped to a
tenant, which is the whole point of the separation. They are therefore
RLS-exempt by construction, exactly like `companies`/`users`, with the same
compensating control: every query lives in `platform_admin.service`, and
`backend/.importlinter` forbids any tenant module from importing this package.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id


class PlatformAdmin(Base, TimestampMixin):
    """Vendor staff. Never a row in `users`, never merged with `is_owner`
    (ADR-BOS-009 §Decision). `is_active` is the entire permission model — a
    vendor RBAC tier is explicitly rejected for v1."""

    __tablename__ = "platform_admins"
    __table_args__ = (
        # Same shape as users' login identifier: case-insensitive uniqueness.
        Index("uq_platform_admins_email_lower", func.lower(text("email")), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    name: Mapped[str]
    email: Mapped[str]
    password_hash: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)


class PlatformAdminSession(Base):
    """The distinct session kind ADR-BOS-009 requires. A separate table rather
    than a `kind` discriminator on `sessions`, because that table's `company_id`
    and `user_id` are both NOT NULL FKs — a vendor session has neither, and
    making them nullable would weaken every tenant-scoping assumption built on
    them."""

    __tablename__ = "platform_admin_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    platform_admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_admins.id"))
    token_hash: Mapped[str] = mapped_column(unique=True)
    csrf_token: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)


class PlatformAuditLog(Base):
    """Append-only record of Vendor Control Plane actions (ADR-BOS-009
    §Audit logging). Deliberately NOT the tenant `audit_log`: that table's
    `user_id` FK is typed to `users.id`, and a dual-typed actor column is the
    "generic entity replacing a concrete one" anti-goal (docs/business-os/00 §7).

    `platform_admin_id` is nullable so a failed login — where no admin is
    authenticated — can still be recorded; `company_id` is nullable because
    plenty of vendor actions have no single target company. Non-company targets
    are described in `detail`, not in a generic target_type/target_id pair.

    `company_id` carries **no ORM-level ForeignKey**, deliberately — the
    constraint exists in the database (migration 0012) where it belongs, but
    declaring it here would make this mapper unusable unless
    `business_os.identity.models` happens to be imported into the same
    metadata, and the vendor plane may not import that module (protected
    boundary). Found the hard way: the bootstrap CLI, which imports only this
    package, died on `NoReferencedTableError` at its first flush. A cross-plane
    reference belongs to the schema, not to the mapper.

    UPDATE/DELETE are blocked by a DB trigger (migration 0012), the same
    role-independent discipline `timeline_events` and `ps_deadline_changes` use.
    """

    __tablename__ = "platform_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    platform_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("platform_admins.id"), default=None
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), default=None)
    action: Mapped[str]
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'"))
    reason: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
