"""Migration #13: vendor session observability + mandatory audit correlation.

A narrow hardening follow-up to migration 0012 (ADR-BOS-009), ahead of Company
Provisioning:

- `platform_admin_sessions.user_agent`/`.client_label` — diagnostic metadata
  for a future "active sessions" screen (not built in this slice). Both
  nullable; neither is ever auto-populated except `user_agent`, captured
  verbatim (bounded) from the HTTP header at login.
- `platform_audit_log.request_id` — ties every vendor audit row to the HTTP
  request or CLI run that wrote it (business_os.shared_kernel.correlation).
  Added NOT NULL directly: this table shipped in migration 0012 within the
  same development cycle and carries no rows from any deployed environment
  (ADR-017's forward-only policy governs *deployed* environments, not local
  dev history) — a `server_default` backfills any local test rows that exist,
  then is dropped so every future INSERT must supply a real value via
  `platform_admin.audit.record()`, whose `request_id` parameter has no
  default (see that module).

No tenant table or RLS policy is touched by either change.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("platform_admin_sessions", sa.Column("user_agent", sa.String(), nullable=True))
    op.add_column("platform_admin_sessions",
                  sa.Column("client_label", sa.String(), nullable=True))

    op.add_column(
        "platform_audit_log",
        sa.Column("request_id", UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
    )
    # Backfill-only default: real correlation ids come from the application
    # (business_os.shared_kernel.correlation), not from the database.
    op.alter_column("platform_audit_log", "request_id", server_default=None)


def downgrade() -> None:
    op.drop_column("platform_audit_log", "request_id")
    op.drop_column("platform_admin_sessions", "client_label")
    op.drop_column("platform_admin_sessions", "user_agent")
