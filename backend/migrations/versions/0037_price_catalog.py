"""Migration #37: price catalog + order-level adjustment line (WP-I, Q12/Q13,
ADR-BOS-013).

Three independent, additive changes:

1. `catalog_items` — the shop's own price list (`serviceflow.catalog`, a new
   RepairFlow module). Flat shape, no categories/variants: `kind` (part|labor),
   `name`, optional `code` (unique per company when set), `unit` (pcs|hour),
   `sale_price` (net), optional `unit_cost` (Owner-only visibility, enforced at
   the API layer), `archived_at` (items are archived, never deleted — order
   lines may still reference them). RLS FORCE, same tenant-isolation policy
   every tenant table carries.

2. `order_adjustments` — the only way to correct an order's price (resolves
   docs/01 OQ-5): signed `amount` + mandatory `reason`, Owner-only at the API
   layer, append-only (no update/delete path). RLS FORCE.

3. `part_lines`/`labor_lines` gain `catalog_item_id` (nullable FK — NULL on
   every existing line, which stays hand-written/free-text forever per Q13c;
   new lines after this migration are catalog-only, enforced in the service
   layer, not by a NOT NULL here) and a `code` snapshot column.
   `labor_lines` additionally gains `unit` (backfilled 'pcs' — every existing
   labor line is fixed-price, not hourly) and `unit_cost` (nullable snapshot,
   NULL on existing rows — no cost data was ever captured before the
   catalog). `labor_lines.qty` and `invoice_lines.qty` change from integer to
   numeric(10,2) so hourly labor (1.5 ч.) can be recorded and invoiced
   (ADR-BOS-013 §8) — existing integer values convert losslessly.

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0037"
down_revision = "0036"
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
    # --- 1. catalog_items ----------------------------------------------------
    op.create_table(
        "catalog_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_catalog_items_company_id_companies"),
                  nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("sale_price", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_catalog_items_company_id", "catalog_items", ["company_id"])
    op.create_index(
        "uq_catalog_items_company_id_code", "catalog_items", ["company_id", "code"],
        unique=True, postgresql_where=sa.text("code IS NOT NULL"),
    )
    op.execute(_rls("catalog_items"))

    # --- 2. order_adjustments -------------------------------------------------
    op.create_table(
        "order_adjustments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_order_adjustments_company_id_companies"),
                  nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id",
                                name="fk_order_adjustments_order_id_service_orders"),
                  nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_order_adjustments_created_by_users"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_order_adjustments_order_id", "order_adjustments", ["order_id"])
    op.execute(_rls("order_adjustments"))

    # --- 3. part_lines / labor_lines: catalog reference + snapshot columns ---
    op.add_column("part_lines", sa.Column(
        "catalog_item_id", UUID(as_uuid=True),
        sa.ForeignKey("catalog_items.id", name="fk_part_lines_catalog_item_id_catalog_items"),
        nullable=True,
    ))
    op.add_column("part_lines", sa.Column("code", sa.String(), nullable=True))

    op.add_column("labor_lines", sa.Column(
        "catalog_item_id", UUID(as_uuid=True),
        sa.ForeignKey("catalog_items.id", name="fk_labor_lines_catalog_item_id_catalog_items"),
        nullable=True,
    ))
    op.add_column("labor_lines", sa.Column("code", sa.String(), nullable=True))
    op.add_column("labor_lines", sa.Column(
        "unit", sa.String(), nullable=False, server_default="pcs",
    ))
    op.add_column("labor_lines", sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True))

    op.alter_column(
        "labor_lines", "qty", type_=sa.Numeric(10, 2), existing_type=sa.Integer(),
        postgresql_using="qty::numeric(10,2)",
    )
    op.alter_column(
        "invoice_lines", "qty", type_=sa.Numeric(10, 2), existing_type=sa.Integer(),
        postgresql_using="qty::numeric(10,2)",
    )


def downgrade() -> None:
    op.alter_column(
        "invoice_lines", "qty", type_=sa.Integer(), existing_type=sa.Numeric(10, 2),
        postgresql_using="qty::integer",
    )
    op.alter_column(
        "labor_lines", "qty", type_=sa.Integer(), existing_type=sa.Numeric(10, 2),
        postgresql_using="qty::integer",
    )
    op.drop_column("labor_lines", "unit_cost")
    op.drop_column("labor_lines", "unit")
    op.drop_column("labor_lines", "code")
    op.drop_column("labor_lines", "catalog_item_id")
    op.drop_column("part_lines", "code")
    op.drop_column("part_lines", "catalog_item_id")
    op.drop_table("order_adjustments")
    op.drop_table("catalog_items")
