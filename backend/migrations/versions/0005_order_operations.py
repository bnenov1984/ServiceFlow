"""Migration #5: diagnoses, part_lines, labor_lines, accessory_items, tasks.

Diagnosis/PartLine/LaborLine/AccessoryItem are IN the ServiceOrder aggregate
(docs/01 §4). Task is deliberately OUTSIDE it (independent lifecycle) but still
RLS-covered like every other tenant table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _rls(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);
"""


def upgrade() -> None:
    op.create_table(
        "diagnoses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_diagnoses_company_id_companies"),
                  nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id", name="fk_diagnoses_order_id"),
                  nullable=False),
        sa.Column("observed", sa.String(), nullable=False, server_default=""),
        sa.Column("cause", sa.String(), nullable=False, server_default=""),
        sa.Column("recommendation", sa.String(), nullable=False, server_default=""),
        sa.Column("estimated_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("estimated_days", sa.Integer(), nullable=True),
        sa.Column("repairable", sa.Boolean(), nullable=True),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approval", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("uq_diagnoses_order_id", "diagnoses", ["order_id"], unique=True)
    op.execute(_rls("diagnoses"))

    op.create_table(
        "part_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_part_lines_company_id_companies"),
                  nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id", name="fk_part_lines_order_id"),
                  nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("state", sa.String(), nullable=False, server_default="needed"),
        sa.CheckConstraint(
            "state IN ('needed', 'ordered', 'received', 'installed', 'removed')",
            name="ck_part_lines_state",
        ),
    )
    op.create_index("ix_part_lines_order_id", "part_lines", ["order_id"])
    op.execute(_rls("part_lines"))

    op.create_table(
        "labor_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_labor_lines_company_id_companies"),
                  nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id", name="fk_labor_lines_order_id"),
                  nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("performed_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_labor_lines_performed_by_users"),
                  nullable=True),
    )
    op.create_index("ix_labor_lines_order_id", "labor_lines", ["order_id"])
    op.execute(_rls("labor_lines"))

    op.create_table(
        "accessory_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_accessory_items_company_id_companies"),
                  nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id", name="fk_accessory_items_order_id"),
                  nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("returned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_accessory_items_order_id", "accessory_items", ["order_id"])
    op.execute(_rls("accessory_items"))

    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_tasks_company_id_companies"),
                  nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id", name="fk_tasks_order_id"),
                  nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("assignee_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_tasks_assignee_id_users"),
                  nullable=True),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("note", sa.String(), nullable=False, server_default=""),
        sa.Column("is_call", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_tasks_created_by_users"),
                  nullable=False),
        sa.Column("completed_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_tasks_completed_by_users"),
                  nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tasks_order_id", "tasks", ["order_id"])
    op.create_index("ix_tasks_company_open", "tasks", ["company_id", "is_done"])
    op.execute(_rls("tasks"))


def downgrade() -> None:
    op.drop_table("tasks")
    op.drop_table("accessory_items")
    op.drop_table("labor_lines")
    op.drop_table("part_lines")
    op.drop_table("diagnoses")
