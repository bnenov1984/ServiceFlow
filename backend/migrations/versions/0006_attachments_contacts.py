"""Migration #6: attachments, contact_records. Both outside the ServiceOrder
aggregate (docs/01 §4) but RLS-covered like every tenant table.

contact_records.type includes "note" as a 5th value beyond the four communication
channels (docs/08 §1: enums are cheap to extend) — see contacts/models.py docstring.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
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
        "attachments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_attachments_company_id_companies"),
                  nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id", name="fk_attachments_order_id"),
                  nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("thumbnail_key", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False, server_default="other"),
        sa.Column("caption", sa.String(), nullable=False, server_default=""),
        sa.Column("mime", sa.String(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_attachments_uploaded_by_users"),
                  nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('photo', 'document')", name="ck_attachments_kind"),
        sa.CheckConstraint(
            "stage IN ('reception', 'progress', 'completed', 'other')",
            name="ck_attachments_stage",
        ),
    )
    op.create_index("ix_attachments_order_id", "attachments", ["order_id"])
    op.create_index("ix_attachments_storage_key", "attachments", ["storage_key"])
    op.execute(_rls("attachments"))

    op.create_table(
        "contact_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_contact_records_company_id_companies"),
                  nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", name="fk_contact_records_customer_id"),
                  nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_orders.id", name="fk_contact_records_order_id"),
                  nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=True),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_contact_records_user_id_users"),
                  nullable=False),
        sa.Column("frozen_after", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "type IN ('call', 'email', 'message', 'visit', 'note')",
            name="ck_contact_records_type",
        ),
        sa.CheckConstraint(
            "direction IN ('in', 'out') OR direction IS NULL",
            name="ck_contact_records_direction",
        ),
        sa.CheckConstraint(
            "(type = 'note' AND direction IS NULL) OR (type != 'note' AND direction IS NOT NULL)",
            name="ck_contact_records_note_no_direction",
        ),
    )
    op.create_index("ix_contact_records_customer_id", "contact_records", ["customer_id"])
    op.create_index("ix_contact_records_order_id", "contact_records", ["order_id"])
    op.execute(_rls("contact_records"))


def downgrade() -> None:
    op.drop_table("contact_records")
    op.drop_table("attachments")
