"""Migration #14: subscription/licence baseline columns on `companies`
(ADR-BOS-012, docs/business-os/18 §6.3), needed by the Company Provisioning
Foundation slice (§9 phase 2).

`subscription_state` keeps its `server_default='active'` permanently rather
than dropping it after backfill (contrast migration 0013's `request_id`,
whose default WAS dropped): every existing/local company needs a value with
no code change (BOS-18 §6.3's own backfill instruction), and
`identity.service.seed_company` (the dev/CLI creation path, unrelated to the
Vendor Control Plane) keeps relying on that default going forward too — only
`ProvisionCompany()` ever explicitly writes `'trial'`.

No tenant table or RLS policy is touched — `companies` is RLS-exempt
(ADR-016 note), unchanged by this migration.

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column(
        "subscription_state", sa.String(), nullable=False, server_default="active",
    ))
    op.add_column("companies", sa.Column(
        "subscription_state_changed_at", sa.DateTime(), nullable=False,
        server_default=sa.func.now(),
    ))
    op.add_column("companies", sa.Column("trial_ends_at", sa.DateTime(), nullable=True))
    op.add_column("companies", sa.Column("seat_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "seat_limit")
    op.drop_column("companies", "trial_ends_at")
    op.drop_column("companies", "subscription_state_changed_at")
    op.drop_column("companies", "subscription_state")
