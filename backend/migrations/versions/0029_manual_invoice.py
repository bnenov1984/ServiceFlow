"""Migration #29: manual invoice support (Wave 6 Issue 30, second half).

Two additive/relaxing changes, bundled (same feature):

1. `invoices.order_id` relaxed from NOT NULL to nullable — a manual invoice
   (created from the central /invoices workspace, no ServiceOrder involved)
   has no order to reference. Every existing row already has a real
   order_id and is completely unaffected; this only widens what a *future*
   row may contain.

2. `invoices.customer_id` — a new nullable FK to `customers`, the buyer-
   identity source for a manual invoice (an order-generated invoice keeps
   resolving its buyer through `order.customer_id`, exactly as before — see
   commercial/service.py's `issue()`). No backfill: every historical
   order-generated invoice's customer remains resolvable through its
   ServiceOrder, so backfilling this column onto them would be redundant,
   never-read data, not a real gap.

Domain invariant (enforced in application code, not a DB CHECK — this
schema alone can't cheaply express "at least one of two nullable FKs is
set" without a cross-column constraint the rest of this codebase doesn't
otherwise use): every Invoice row has *exactly one* buyer-identity source —
`order_id` (buyer resolved via the order's customer) XOR `customer_id`
(buyer resolved directly). Both creation paths (`create_draft`/
`create_manual_draft`) already guarantee this by construction.

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("invoices", "order_id", existing_type=UUID(as_uuid=True), nullable=True)
    op.add_column("invoices", sa.Column("customer_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_invoices_customer_id_customers", "invoices", "customers",
        ["customer_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_invoices_customer_id_customers", "invoices", type_="foreignkey")
    op.drop_column("invoices", "customer_id")
    op.alter_column("invoices", "order_id", existing_type=UUID(as_uuid=True), nullable=False)
