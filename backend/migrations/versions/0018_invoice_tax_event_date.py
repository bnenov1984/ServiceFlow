"""Migration #18: invoices.tax_event_date (docs/ACCOUNTANT_REVIEW.md §2).

Invoice-numbering-prerequisite-style slice: schema/API only, no Issue
behavior. ЗДДС чл. 114, ал. 1 requires the date on which the tax event (or
an advance payment) occurred as its own invoice element, legally distinct
from the issue date (`issued_at`). Nullable, no server default, no
backfill: every existing row and every Draft this slice creates has no
finalized taxable-event date yet — assigning one is explicitly a future
Issue-workflow responsibility, not this migration's or any code touched by
this slice.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("tax_event_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "tax_event_date")
