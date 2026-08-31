"""Migration #21: "testing" is no longer an active order status (Wave 2
Issue 5, product decision) — it is folded into "repair", not deleted from
history. Every existing order still sitting in `status_code = 'testing'` is
reassigned to `'repair'`; the now-unreferenced `order_statuses` row is then
dropped so the FK stays clean.

Data + one row delete, not a structural schema change. `service_orders.
status_code`'s FK to `order_statuses.code` (migration 0004) requires the
reassignment to happen strictly before the row delete — reversed order would
violate the constraint on any company still holding a testing order.

TimelineEvent rows already recorded with `data.to == "testing"` (or `.from`)
are untouched — append-only, never rewritten (BR-5); this migration changes
only the current, still-open `service_orders.status_code` value, never
historical event data.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE service_orders SET status_code = 'repair' WHERE status_code = 'testing'"
    ))
    bind.execute(sa.text("DELETE FROM order_statuses WHERE code = 'testing'"))


def downgrade() -> None:
    # Best-effort, local-dev-reset only (docs/04 §3 / ADR-017: forward-only
    # governs *deployed* environments, not this) — restores the order_statuses
    # row so the schema is symmetric again. Cannot restore which orders were
    # actually "testing" before upgrade() reassigned them; that information
    # is gone by design, same as migration 0016/0020's own downgrade posture.
    bind = op.get_bind()
    bind.execute(sa.text(
        "INSERT INTO order_statuses (code, kind, name_bg, sort) "
        "VALUES ('testing', 'working', 'Тестване', 6) "
        "ON CONFLICT (code) DO NOTHING"
    ))
