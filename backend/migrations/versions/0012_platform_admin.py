"""Migration #12: Vendor Control Plane foundation — platform_admins,
platform_admin_sessions, platform_audit_log (ADR-BOS-009,
docs/business-os/18 §6.1/§6.2, §9 phase 1).

Vendor identity is structurally separate from tenant identity, permanently: no
`company_id` on any table here, no row in `users`, no reuse of `sessions`
(whose `company_id`/`user_id` are NOT NULL FKs a vendor session cannot supply).

RLS: all three tables are exempt, for the same reason `companies`/`users` are —
there is no `company_id` to key a policy on. The compensating control is the
same one ADR-016 already accepts: every query lives in
`business_os.platform_admin.service`, and `backend/.importlinter` forbids any
tenant module from importing that package. `platform_audit_log.company_id` is a
*target* reference, not a tenancy scope: RLS'ing on it would lock the vendor
plane (which sets no GUC) out of its own audit trail.

platform_audit_log is append-only, enforced by a trigger rather than by
convention — role-independent, same discipline as `timeline_events` (0004) and
`ps_deadline_changes` (0011).

`platform_audit_log.company_id`'s foreign key is declared **here only**, not on
the SQLAlchemy model: the vendor plane must not import `identity.models`, so
that table's mapper is absent whenever only `business_os.platform_admin` is
loaded (the bootstrap CLI does exactly that, and an ORM-level FK made it die at
its first flush). The database still enforces referential integrity — see the
note on `PlatformAuditLog` for the reasoning.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

APPEND_ONLY = """
CREATE FUNCTION platform_audit_log_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'platform_audit_log is append-only (ADR-BOS-009)';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER platform_audit_log_no_rewrite
    BEFORE UPDATE OR DELETE ON platform_audit_log
    FOR EACH ROW EXECUTE FUNCTION platform_audit_log_append_only();
"""


def upgrade() -> None:
    op.create_table(
        "platform_admins",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("uq_platform_admins_email_lower", "platform_admins",
                    [sa.text("lower(email)")], unique=True)

    op.create_table(
        "platform_admin_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("platform_admin_id", UUID(as_uuid=True),
                  sa.ForeignKey("platform_admins.id",
                                name="fk_platform_admin_sessions_platform_admin_id_platform_admins"),
                  nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("csrf_token", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_platform_admin_sessions_platform_admin_id",
                    "platform_admin_sessions", ["platform_admin_id"])

    op.create_table(
        "platform_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("platform_admin_id", UUID(as_uuid=True),
                  sa.ForeignKey("platform_admins.id",
                                name="fk_platform_audit_log_platform_admin_id_platform_admins"),
                  nullable=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_platform_audit_log_company_id_companies"),
                  nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("detail", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_platform_audit_log_created_at", "platform_audit_log", ["created_at"])
    op.create_index("ix_platform_audit_log_company_id", "platform_audit_log",
                    ["company_id", "created_at"])
    op.execute(APPEND_ONLY)


def downgrade() -> None:
    # Forward-only policy in deployed environments (04 §3, carried by ADR-017);
    # downgrade exists for local development resets only.
    op.execute("DROP TRIGGER platform_audit_log_no_rewrite ON platform_audit_log")
    op.execute("DROP FUNCTION platform_audit_log_append_only()")
    op.drop_table("platform_audit_log")
    op.drop_table("platform_admin_sessions")
    op.drop_table("platform_admins")
