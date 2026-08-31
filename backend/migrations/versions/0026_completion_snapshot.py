"""Migration #26: service_orders.completion_snapshot (Wave 4 Issue 7).

Additive only — a nullable JSONB column, no CHECK constraint (its shape is
owned and validated entirely by `service_orders.service._build_completion_
snapshot`, the same way `commercial.invoices.seller`/`.buyer` carry no DB-
level shape constraint either).

No backfill: historical delivered orders get NULL, by design — reconstructing
a plausible-looking snapshot from whatever live data happens to exist today
would misrepresent what was actually true at each order's real delivery time
(docs/business-os Wave 4 audit's explicit "no fake historical delivery
protocol" decision). `GET /orders/{id}/protocol.pdf?type=delivery` treats a
NULL snapshot as "protocol unavailable" regardless of *why* it's NULL (never
delivered vs. delivered before this column existed) — the migration doesn't
need to distinguish the two.

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("service_orders", sa.Column("completion_snapshot", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("service_orders", "completion_snapshot")
