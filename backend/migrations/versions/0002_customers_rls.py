"""Migration #2: customers — the first domain table, and with it RLS enforcement.

RLS design (ADR-016): policies key on current_setting('app.company_id'). The GUC is
set per-request by the tenant dependency via set_config(). FORCE ROW LEVEL SECURITY
matters: the app role owns the tables and would otherwise bypass policies. With the
GUC unset the policy evaluates NULL → zero rows (fail closed).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

RLS = """
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON customers
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);
"""


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_customers_company_id_companies"),
                  nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("phone2", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("is_company", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("company_requisites", JSONB(), nullable=True),
        sa.Column("notes", sa.String(), nullable=False, server_default=""),
        sa.Column("phone_normalized", sa.String(), nullable=False),
        sa.Column("name_translit", sa.String(), nullable=False),
        sa.Column("anonymized_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_customers_company_id", "customers", ["company_id"])
    op.create_index("ix_customers_phone_normalized", "customers",
                    ["company_id", "phone_normalized"])
    op.execute(
        "CREATE INDEX ix_customers_name_trgm ON customers "
        "USING gin (name_translit gin_trgm_ops)"
    )
    op.execute(RLS)


def downgrade() -> None:
    op.drop_table("customers")
