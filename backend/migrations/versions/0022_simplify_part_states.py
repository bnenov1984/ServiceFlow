"""Migration #22: part_lines.state simplified to the V1 model (Wave 2 Issue
33) — "ordered" (assigned/requested for this order, regardless of physical
stock) and "installed" only. The original 5-state model (migration 0005:
needed/ordered/received/installed/removed) is folded per the product's
legacy mapping:

    needed    -> ordered
    ordered   -> ordered  (unchanged)
    received  -> ordered
    removed   -> ordered
    installed -> installed (unchanged)

Order of operations matters: backfill the data first, THEN tighten the
`ck_part_lines_state` CHECK constraint and the column default — doing it the
other way round would reject the very rows being backfilled. No inventory/
stock concept is introduced; this only narrows an existing free-standing
`state` string. Historical `TimelineEvent` rows (`part_added`, `part_ordered`,
`part_received`, `part_state_changed`) are untouched — this migration never
touches `timeline_events`.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE part_lines SET state = 'ordered' "
        "WHERE state IN ('needed', 'received', 'removed')"
    ))
    op.drop_constraint("ck_part_lines_state", "part_lines", type_="check")
    op.create_check_constraint(
        "ck_part_lines_state", "part_lines", "state IN ('ordered', 'installed')",
    )
    op.alter_column("part_lines", "state", server_default="ordered")


def downgrade() -> None:
    # Best-effort, local-dev-reset only (docs/04 §3 / ADR-017: forward-only
    # governs *deployed* environments, not this) — restores the wider
    # constraint/default so the schema is symmetric again. Cannot restore
    # which rows were originally needed/received/removed before upgrade()
    # folded them into "ordered"; that distinction is gone by design, same
    # posture as migrations 0016/0020/0021's own downgrades.
    op.alter_column("part_lines", "state", server_default="needed")
    op.drop_constraint("ck_part_lines_state", "part_lines", type_="check")
    op.create_check_constraint(
        "ck_part_lines_state", "part_lines",
        "state IN ('needed', 'ordered', 'received', 'installed', 'removed')",
    )
