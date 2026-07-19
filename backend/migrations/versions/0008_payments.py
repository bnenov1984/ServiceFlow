"""Migration #8: payments (docs/01 §Payment, docs/08 §commercial).

First table of Commercial Documents & Invoicing. Payment lands ahead of
Invoice — no numbering, no immutability, no VAT rules — and docs/08 already
declares invoice_id nullable, so a payment never needs an invoice to exist.
`invoice_id` intentionally carries no FK constraint: the `invoices` table
does not exist yet. The future Invoice migration adds
`fk_payments_invoice_id_invoices` once it does; this migration must not
create a placeholder `invoices` table to work around that.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0008"
down_revision = "0007"
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
        "payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_payments_company_id_companies"),
                  nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id", name="fk_payments_order_id"),
                  nullable=False),
        # No FK yet — the invoices table does not exist (see module docstring).
        sa.Column("invoice_id", UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("is_refund", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("note", sa.String(), nullable=False, server_default=""),
        sa.Column("received_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_payments_received_by_users"),
                  nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint(
            "method IN ('cash', 'card', 'bank')", name="ck_payments_method",
        ),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index("ix_payments_company_id", "payments", ["company_id"])
    op.execute(_rls("payments"))


def downgrade() -> None:
    op.drop_table("payments")
