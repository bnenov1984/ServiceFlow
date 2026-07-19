"""Migration #1: identity bootstrap — companies, users, sessions, audit_log.

Identity tables are the RLS-exempt tenant bootstrap (queries centralized in
business_os.identity.service — ADR-016 note). RLS policies begin with the first
domain-table migration. pg_trgm enabled here once for the search work ahead
(ADR-010).

Revision ID: 0001
Revises:
Create Date: 2026-07-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "companies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("requisites", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("vat_registered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("settings", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_users_company_id_companies"),
                  nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("pin_hash", sa.String(), nullable=True),
        sa.Column("is_owner", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("language", sa.String(), nullable=False, server_default="bg"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_company_id", "users", ["company_id"])
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_sessions_company_id_companies"),
                  nullable=False),
        sa.Column("login_user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_sessions_login_user_id_users"),
                  nullable=False),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_sessions_user_id_users"),
                  nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("csrf_token", sa.String(), nullable=False),
        sa.Column("device_label", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sessions_company_id", "sessions", ["company_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_audit_log_company_id_companies"),
                  nullable=False),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_audit_log_user_id_users"),
                  nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("detail", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_company_id", "audit_log", ["company_id", "created_at"])


def downgrade() -> None:
    # Forward-only policy in deployed environments (04 §3, carried by ADR-017);
    # downgrade exists for local development resets only.
    op.drop_table("audit_log")
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("companies")
