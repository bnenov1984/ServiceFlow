"""Migration #25: part_lines.warranty_days (Wave 4 PART WARRANTY).

Additive only, no new warranty entity/table — the audit found PartLine had no
date/duration field to reuse, so this is the smallest clean addition: NULL =
not specified, 0 = explicitly "Без гаранция", positive = days. No historical
backfill: every existing part line simply has no warranty on file, which is
the honest state (it was never recorded), not a fact to invent.

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("part_lines", sa.Column("warranty_days", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_part_lines_warranty_days_non_negative", "part_lines",
        "warranty_days IS NULL OR warranty_days >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_part_lines_warranty_days_non_negative", "part_lines",
                       type_="check")
    op.drop_column("part_lines", "warranty_days")
