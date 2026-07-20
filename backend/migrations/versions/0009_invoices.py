"""Migration #9: invoices, invoice_lines (docs/01 §Invoice, docs/08 §commercial).

Invoice Draft slice only — schema matches the frozen docs/08 shape in full
(so a later slice never needs to ALTER TABLE to add issue/PDF/VAT columns),
but this migration ships no numbering, issue, annul/reissue, or PDF
behavior. `number`, `issued_at`, `seller`, `buyer`, `net`/`vat`/`gross`,
`annuls_invoice_id`, `annul_reason`, `pdf_storage_key` all stay NULL for
every row this slice creates — status is always 'draft'. `document_sequences`
is untouched: numbering ownership is still Open (docs/business-os/05 §1,
BOS-09 Q2) and this slice never calls it.

Also fulfills a promise from migration 0008: `payments.invoice_id` was
nullable with no FK because `invoices` didn't exist yet. It exists now, so
this migration adds `fk_payments_invoice_id_invoices` — pure referential
integrity, unrelated to issue/numbering/PDF/VAT.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0009"
down_revision = "0008"
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
        "invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_invoices_company_id_companies"),
                  nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id", name="fk_invoices_order_id"),
                  nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("number", sa.BigInteger(), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("seller", JSONB(), nullable=True),
        sa.Column("buyer", JSONB(), nullable=True),
        sa.Column("vat_mode", sa.String(), nullable=True),
        sa.Column("net", sa.Numeric(10, 2), nullable=True),
        sa.Column("vat", sa.Numeric(10, 2), nullable=True),
        sa.Column("gross", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("annuls_invoice_id", UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", name="fk_invoices_annuls_invoice_id"),
                  nullable=True),
        sa.Column("annul_reason", sa.String(), nullable=True),
        sa.Column("pdf_storage_key", sa.String(), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('draft', 'issued', 'annulled')", name="ck_invoices_status",
        ),
        sa.CheckConstraint(
            "vat_mode IN ('registered', 'not_registered') OR vat_mode IS NULL",
            name="ck_invoices_vat_mode",
        ),
    )
    op.create_index("ix_invoices_order_id", "invoices", ["order_id"])
    op.create_index("ix_invoices_company_id", "invoices", ["company_id"])
    op.create_index(
        "uq_invoices_company_id_number", "invoices", ["company_id", "number"],
        unique=True, postgresql_where=sa.text("number IS NOT NULL"),
    )
    op.execute(_rls("invoices"))

    op.create_table(
        "invoice_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_invoice_lines_company_id_companies"),
                  nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", name="fk_invoice_lines_invoice_id"),
                  nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint(
            "source IN ('labor', 'part', 'manual', 'adjustment')",
            name="ck_invoice_lines_source",
        ),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])
    op.execute(_rls("invoice_lines"))

    op.create_foreign_key(
        "fk_payments_invoice_id_invoices", "payments", "invoices",
        ["invoice_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_payments_invoice_id_invoices", "payments", type_="foreignkey")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
