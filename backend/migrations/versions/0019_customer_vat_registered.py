"""Migration #19: customers.vat_registered (docs/ACCOUNTANT_REVIEW.md §4 B1).

Customer VAT-identity prerequisite slice: schema/API only, no Invoice Issue
behavior. Company customers currently have no way to record whether they
are VAT-registered, so a future B2B Issue workflow cannot tell a
non-VAT-registered company buyer apart from a VAT-registered one (the exact
gap the read-only B2B investigation stopped on). Nullable, no server
default, no backfill: every existing company Customer — and every new one
created without an explicit choice — must read back UNKNOWN
(`vat_registered IS NULL`), never `false`. Treating an unconfirmed buyer as
"confirmed not VAT-registered" would be exactly the silent guess Phase A's
own architecture was built to avoid.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("vat_registered", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "vat_registered")
