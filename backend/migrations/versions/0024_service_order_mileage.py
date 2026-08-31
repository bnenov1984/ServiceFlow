"""Migration #24: service_orders.mileage (Wave 3 Issues 21/26/27).

Mileage belongs primarily to the service visit, not just the vehicle master
record — this adds one nullable column, captured (optionally) at intake for
automotive orders. `service_orders.created_at` already serves as the visit
timestamp; no separate date column is added.

Additive only: NULL for every existing/legacy order, no backfill possible or
attempted — a mileage reading that was never recorded cannot be reconstructed,
and `serviceflow.assets.service` / the read side keep falling back to the
legacy `Asset.field_values["mileage"]` for a vehicle with no order-level
reading yet (application-layer fallback, not a schema concern here).

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("service_orders", sa.Column("mileage", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_service_orders_mileage_non_negative", "service_orders",
        "mileage IS NULL OR mileage >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_service_orders_mileage_non_negative", "service_orders",
                       type_="check")
    op.drop_column("service_orders", "mileage")
