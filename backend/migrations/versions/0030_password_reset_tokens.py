"""Migration #30: password_reset_tokens (Tenant Forgot Password V1).

Identity-owned, same RLS-exempt bootstrap posture as `sessions`/`audit_log`
(migration 0001's own docstring: "Identity tables are the RLS-exempt tenant
bootstrap ... RLS policies begin with the first domain-table migration") —
no `ENABLE ROW LEVEL SECURITY` here, matching every other identity table.

No `company_id` column: a reset token is looked up by `token_hash` alone
(never listed per-tenant), and the owning company is already reachable via
`user_id` -> `users.company_id` — the same reasoning `sessions.company_id`
exists for (query convenience, not a real ownership need) doesn't apply here
since nothing queries this table by company.

`token_hash` stores only `sha256(raw_token)` (`shared_kernel.passwords.
hash_token`) — the raw opaque token (`new_session_token()`) is never
persisted anywhere, mirroring `sessions.token_hash` exactly. `used_at`
follows `sessions.revoked_at`'s own convention: NULL = still live/unused,
a timestamp = consumed (single-use, never deleted so a re-presented token
still resolves to a real, auditable, correctly-rejected row).

`ix_password_reset_tokens_user_id` backs "invalidate every other unused
token for this user" (both on a fresh reset request and on a successful
reset) — the only per-user query this table needs.

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_password_reset_tokens_user_id_users"),
                  nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
