"""Migration #38 (order-workflow-revamp WP-J, Q14/Q14b/Q14c/Q15/Q15b): part_lines
gains a third state and swaps its months-based warranty field for a boolean.

State: widens `ck_part_lines_state` from ('ordered', 'installed') to
('issued', 'ordered', 'installed') — "ordered" and "installed" keep their
exact prior meaning and literal value (migration 0022's "ordered" already
meant "assigned/requested, regardless of physical stock"; Q15b narrows that
to specifically мeaning поръчана/"must be ordered in", with "issued" now
covering "available from the shop's own supply"). No data backfill needed:
every existing row's value (`ordered` or `installed`) is still a member of
the widened set, unlike 0022's narrowing, which is why this migration can
skip the "backfill first, then constrain" two-step 0022 needed.

Warranty: drops `warranty_days` (months-at-the-API-boundary, migration 0025)
in favor of `has_warranty: bool NOT NULL DEFAULT true` (Q14c: on by default).
The warranty *term* itself is no longer per-line — it was always just the
company-wide text already frozen into the delivery protocol's "Гаранционни
условия" section, never actually derived from this column at render time
for anything but the per-line months suffix. Backfill: everything becomes
`true` except a line that explicitly recorded "0 months" (deliberately no
warranty) — a NULL (never specified) is not evidence of "no warranty" and
defaults to `true` same as everything else, consistent with Q14c's
"default on" for every part, old or new. Already-completed orders'
`completion_snapshot` JSON is untouched (frozen, never rewritten) and keeps
printing its stored months forever — this migration only touches the live
`part_lines` table.

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_part_lines_state", "part_lines", type_="check")
    op.create_check_constraint(
        "ck_part_lines_state", "part_lines", "state IN ('issued', 'ordered', 'installed')",
    )
    op.alter_column("part_lines", "state", server_default="issued")

    op.add_column(
        "part_lines",
        sa.Column("has_warranty", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE part_lines SET has_warranty = false WHERE warranty_days = 0"
    ))
    op.drop_constraint("ck_part_lines_warranty_days_non_negative", "part_lines",
                       type_="check")
    op.drop_column("part_lines", "warranty_days")


def downgrade() -> None:
    # Best-effort, local-dev-reset only (docs/04 §3 / ADR-017: forward-only
    # governs *deployed* environments, not this) — same posture as 0022's
    # and 0025's own downgrades. `has_warranty` carries no month/day value to
    # restore, so every row comes back with `warranty_days = NULL` ("not
    # specified"), not a guess. "issued" rows must be folded back into
    # "ordered" *before* narrowing the CHECK constraint, same order-of-
    # operations reason 0022 backfills before constraining — narrowing first
    # would reject the very rows being folded.
    op.add_column("part_lines", sa.Column("warranty_days", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_part_lines_warranty_days_non_negative", "part_lines",
        "warranty_days IS NULL OR warranty_days >= 0",
    )
    op.drop_column("part_lines", "has_warranty")

    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE part_lines SET state = 'ordered' WHERE state = 'issued'"
    ))
    op.alter_column("part_lines", "state", server_default="ordered")
    op.drop_constraint("ck_part_lines_state", "part_lines", type_="check")
    op.create_check_constraint(
        "ck_part_lines_state", "part_lines", "state IN ('ordered', 'installed')",
    )
