"""Migration #28: invoice annulment timestamp (Wave 6 Issue 30).

One additive column: `invoices.annulled_at` (nullable timestamp). The
existing `status="annulled"` enum value and `annul_reason` column
(migration 0009) are reused as-is for the annulment feature — this
migration only adds the one genuinely missing piece, a dedicated timestamp
distinct from the generic, auto-bumping `updated_at` (TimestampMixin), so
"when was this invoice annulled" has its own honest, purpose-built column
rather than being inferred from a column that could in principle be
touched by something else later.

`annuls_invoice_id` (also from migration 0009) is deliberately left alone:
it is reserved for a future reissue-linkage feature, not part of this V1
annulment flow.

No backfill: NULL is the correct, honest value for every existing row (no
invoice has ever been annulled before this feature existed).

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("annulled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "annulled_at")
