"""Migration #31: "delivered"/"Предадена" renamed to "completed"/"Приключена"
(Wave 4 audit correction, product decision 2026-09-25).

The original Wave 4 implementation reused the pre-existing terminal-success
status ("delivered") instead of adding the distinct post-Ready completion
step the PO had actually asked for. Reviewing that divergence, the PO chose
to rename the existing status rather than add a second terminal status —
one terminal_success status, "Приключена", replaces "Предадена" outright.

Same reassign-then-drop pattern as migration 0021 ("testing" -> "repair"):
`service_orders.status_code` FKs to `order_statuses.code` (migration 0004),
so the code value can't just be UPDATEd in place — a row with the new code
must exist before any order can reference it, and the old code must stop
being referenced before its row can be dropped.

Also renames `service_orders.delivered_at` -> `completed_at` (plain column
rename, no FK involved) so the column name matches the new status vocabulary
end to end — this timestamp is read by invoice tax-event-date defaulting
(frontend/src/order/InvoiceDraftEditor.tsx) as well as the completion
protocol, so leaving it named after the old status would be actively
misleading, not just cosmetically stale.

TimelineEvent rows already recorded with `data.to == "delivered"` (or
`event_type == "order_delivered"`) are untouched — append-only, never
rewritten (BR-5). The timeline subscriber's KNOWN_EVENT_TYPES allowlist and
the frontend's event-label map both keep a mapping for the old
"order_delivered" type so historical entries still render correctly; only
newly-written events use "order_completed".

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "INSERT INTO order_statuses (code, kind, name_bg, sort) "
        "VALUES ('completed', 'terminal_success', 'Приключена', 8)"
    ))
    bind.execute(sa.text(
        "UPDATE service_orders SET status_code = 'completed' WHERE status_code = 'delivered'"
    ))
    bind.execute(sa.text("DELETE FROM order_statuses WHERE code = 'delivered'"))
    op.alter_column("service_orders", "delivered_at", new_column_name="completed_at")


def downgrade() -> None:
    # Best-effort, local-dev-reset only (docs/04 §3 / ADR-017: forward-only
    # governs *deployed* environments, not this) — same posture as 0021's
    # downgrade. Cannot restore which orders were "delivered" vs some future
    # "completed"-only order; that distinction is gone by design.
    op.alter_column("service_orders", "completed_at", new_column_name="delivered_at")
    bind = op.get_bind()
    bind.execute(sa.text(
        "INSERT INTO order_statuses (code, kind, name_bg, sort) "
        "VALUES ('delivered', 'terminal_success', 'Предадена', 8) "
        "ON CONFLICT (code) DO NOTHING"
    ))
    bind.execute(sa.text(
        "UPDATE service_orders SET status_code = 'delivered' WHERE status_code = 'completed'"
    ))
    bind.execute(sa.text("DELETE FROM order_statuses WHERE code = 'completed'"))
