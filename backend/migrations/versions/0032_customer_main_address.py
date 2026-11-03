"""Migration #32: individual customer main address (order-workflow-revamp WP-B, Q20).

One additive column: `customers.address` (nullable text) — an individual
customer's own optional main address, free-text/multi-line. A company
customer's main address already lives in `company_requisites.address`
(JSONB, migration predates this one); this column is deliberately the
individual-only counterpart, not a replacement for that.

No backfill: NULL is the correct, honest value for every existing row (no
individual customer has ever had a main address field to fill before now).

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("address", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "address")
