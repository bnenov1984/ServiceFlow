"""Migration #35: mileage-override confirmation flag (WP-D, Q10).

One additive column: `service_orders.mileage_confirmed_lower` — true only
when an Owner explicitly confirmed a mileage reading lower than the asset's
previously recorded maximum (Q9's monotonic rule, bypassed on purpose per
Q10, never a silent correction). Backfilled false for every existing row,
which is correct: the bypass path did not exist before this migration, so
no prior row could have taken it.

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_orders",
        sa.Column("mileage_confirmed_lower", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("service_orders", "mileage_confirmed_lower")
