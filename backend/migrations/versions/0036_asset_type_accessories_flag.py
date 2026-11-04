"""Migration #36: accessories as a per-asset-type flag (WP-H, Q16/Q16b).

One additive column: `asset_types.accessories` — true by default (every
profile keeps the accessories checklist), false for automotive's "vehicle"
type only (Q16: accessories at intake/order/completion are automotive-
specific noise — a car almost never comes with a charger/SIM/box). Nothing
is deleted: existing AccessoryItem rows and historic protocols/completion
snapshots keep rendering regardless of this flag (protocol.py and
CompletionDialog already only render the accessories block when there's
something non-empty to show).

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "asset_types",
        sa.Column("accessories", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
    )
    op.execute(
        "UPDATE asset_types SET accessories = false "
        "WHERE business_profile = 'automotive_repair'"
    )


def downgrade() -> None:
    op.drop_column("asset_types", "accessories")
