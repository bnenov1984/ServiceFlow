"""Migration #27: customer delivery address + order-level logistics
(Wave 5 Issues 11/12).

Two additive changes, bundled (same feature, mirrors migration 0023's
precedent of one migration covering more than one table for one feature):

1. `customers.delivery_address` — a new nullable JSONB column, individual or
   company customer alike. `country` itself needs NO migration: it lives
   inside the already-existing `customers.company_requisites` JSONB blob
   (key "country") — no historical row is rewritten to inject it; the
   application layer treats an absent key as "BG" (every pre-Wave-5 company
   customer's true, only-ever-supported country).

2. `service_orders.delivery_method` (nullable string, "pickup"/"courier",
   validated at the Pydantic layer — no DB CHECK, same precedent as
   `priority`) and `service_orders.delivery_address` (nullable JSONB, a
   plain copy taken at order-creation time, never a live reference back to
   the customer's own address).

No backfill for either table: NULL is the correct, honest value for every
existing row (no delivery address/method was ever recorded before this).

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("delivery_address", JSONB(), nullable=True))
    op.add_column("service_orders", sa.Column("delivery_method", sa.String(), nullable=True))
    op.add_column("service_orders", sa.Column("delivery_address", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("service_orders", "delivery_address")
    op.drop_column("service_orders", "delivery_method")
    op.drop_column("customers", "delivery_address")
