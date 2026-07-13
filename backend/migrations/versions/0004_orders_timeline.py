"""Migration #4: order_statuses seed, document_sequences, service_orders, timeline.

timeline_events append-only is enforced by a trigger — role-independent, so not
even a misbehaving admin session can rewrite history quietly (BR-5, FR-10.2).

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _rls(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);
"""

# Kept in sync with serviceflow.service_orders.statuses (tested in test_statuses).
SEED_STATUSES = [
    ("received", "working", "Приета", 1),
    ("diagnostics", "working", "Диагностика", 2),
    ("waiting_customer", "waiting", "Чака клиент", 3),
    ("waiting_parts", "waiting", "Чака части", 4),
    ("repair", "working", "Ремонт", 5),
    ("testing", "working", "Тестване", 6),
    ("ready", "ready", "Готова", 7),
    ("delivered", "terminal_success", "Предадена", 8),
    ("declined", "terminal_failure", "Отказана", 9),
    ("unrepairable", "terminal_failure", "Неремонтируема", 10),
    ("cancelled", "terminal_failure", "Анулирана", 11),
]


def upgrade() -> None:
    order_statuses = op.create_table(
        "order_statuses",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name_bg", sa.String(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
    )
    op.bulk_insert(order_statuses, [
        {"code": c, "kind": k, "name_bg": n, "sort": s} for c, k, n, s in SEED_STATUSES
    ])

    op.create_table(
        "document_sequences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_document_sequences_company_id_companies"),
                  nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("current", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("uq_document_sequences_key", "document_sequences",
                    ["company_id", "kind", "year"], unique=True)

    op.create_table(
        "service_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_service_orders_company_id_companies"),
                  nullable=False),
        sa.Column("number", sa.String(), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id",
                                name="fk_service_orders_customer_id_customers"),
                  nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True),
                  sa.ForeignKey("assets.id", name="fk_service_orders_asset_id_assets"),
                  nullable=False),
        sa.Column("complaint", sa.String(), nullable=False),
        sa.Column("status_code", sa.String(),
                  sa.ForeignKey("order_statuses.code",
                                name="fk_service_orders_status_code"),
                  nullable=False),
        sa.Column("technician_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_service_orders_technician_id_users"),
                  nullable=True),
        sa.Column("priority", sa.String(), nullable=False, server_default="normal"),
        sa.Column("promised_on", sa.Date(), nullable=True),
        sa.Column("warranty_days", sa.Integer(), nullable=True),
        sa.Column("origin_order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id",
                                name="fk_service_orders_origin_order_id"),
                  nullable=True),
        sa.Column("status_changed_at", sa.DateTime(), nullable=True),
        sa.Column("terminal_reason", sa.String(), nullable=True),
        sa.Column("terminal_at", sa.DateTime(), nullable=True),
        sa.Column("prev_status_code", sa.String(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_service_orders_created_by_users"),
                  nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("priority IN ('normal', 'high')",
                           name="ck_service_orders_priority"),
    )
    op.create_index("uq_service_orders_number", "service_orders",
                    ["company_id", "number"], unique=True)
    op.create_index("ix_service_orders_company_id", "service_orders", ["company_id"])
    op.create_index("ix_service_orders_customer_id", "service_orders", ["customer_id"])
    op.create_index("ix_service_orders_asset_id", "service_orders", ["asset_id"])
    op.create_index("ix_service_orders_status_code", "service_orders", ["status_code"])
    op.create_index("ix_service_orders_promised_on", "service_orders", ["promised_on"],
                    postgresql_where=sa.text("archived_at IS NULL"))
    op.execute(_rls("service_orders"))

    op.create_table(
        "timeline_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_timeline_events_company_id_companies"),
                  nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id",
                                name="fk_timeline_events_order_id_service_orders"),
                  nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_timeline_events_actor_user_id_users"),
                  nullable=True),
        sa.Column("data", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_timeline_events_order", "timeline_events",
                    ["order_id", "created_at"])
    op.execute(_rls("timeline_events"))
    op.execute("""
CREATE FUNCTION timeline_events_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'timeline_events is append-only (BR-5)';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER timeline_events_no_rewrite
    BEFORE UPDATE OR DELETE ON timeline_events
    FOR EACH ROW EXECUTE FUNCTION timeline_events_append_only();
""")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS timeline_events_no_rewrite ON timeline_events")
    op.execute("DROP FUNCTION IF EXISTS timeline_events_append_only")
    op.drop_table("timeline_events")
    op.drop_table("service_orders")
    op.drop_table("document_sequences")
    op.drop_table("order_statuses")
