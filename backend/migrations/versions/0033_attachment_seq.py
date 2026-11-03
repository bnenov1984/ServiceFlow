"""Migration #33: attachment display sequence number (order-workflow-revamp WP-E, Q21).

One additive column: `attachments.seq` — the per-order, upload-order sequence
number used to build the `<order number>_<seq>.<ext>` display/download name
(ADR-007's content-addressed `storage_key` is untouched; this is a
display/download name only, never a storage rename). Backfilled from existing
rows ordered by `created_at` (ties broken by `id`), including soft-deleted
rows — a deleted attachment's number must never be reused by a later upload,
so it needs a real seq of its own, not a gap.

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attachments", sa.Column("seq", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE attachments a
        SET seq = ranked.rn
        FROM (
            SELECT id, row_number() OVER (
                PARTITION BY order_id ORDER BY created_at, id
            ) AS rn
            FROM attachments
        ) AS ranked
        WHERE a.id = ranked.id
    """)
    op.alter_column("attachments", "seq", nullable=False)


def downgrade() -> None:
    op.drop_column("attachments", "seq")
