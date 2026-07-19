"""Migration #7: Professional Services walking skeleton — ps_clients,
ps_assignments, ps_next_actions. First tables of Business OS vertical module
#3 (docs/business-os/17, /modules/professional-services). No configurable
workflow tables, no notifications, no job tables — deliberately trimmed
first slice.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
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
        "ps_clients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_ps_clients_company_id_companies"),
                  nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="person"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('person', 'company')", name="ck_ps_clients_kind"),
    )
    op.create_index("ix_ps_clients_company_id", "ps_clients", ["company_id"])
    op.execute(_rls("ps_clients"))

    op.create_table(
        "ps_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_ps_assignments_company_id_companies"),
                  nullable=False),
        sa.Column("client_id", UUID(as_uuid=True),
                  sa.ForeignKey("ps_clients.id", name="fk_ps_assignments_client_id"),
                  nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False, server_default="intake"),
        sa.Column("lifecycle_state", sa.String(), nullable=False, server_default="active"),
        sa.Column("official_deadline_on", sa.Date(), nullable=True),
        sa.Column("internal_target_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "stage IN ('intake', 'in_progress', 'waiting_client', 'delivered')",
            name="ck_ps_assignments_stage",
        ),
        sa.CheckConstraint(
            "lifecycle_state IN ('active', 'delivered', 'cancelled')",
            name="ck_ps_assignments_lifecycle_state",
        ),
    )
    op.create_index("ix_ps_assignments_company_id", "ps_assignments", ["company_id"])
    op.create_index("ix_ps_assignments_client_id", "ps_assignments", ["client_id"])
    op.execute(_rls("ps_assignments"))

    op.create_table(
        "ps_next_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_ps_next_actions_company_id_companies"),
                  nullable=False),
        sa.Column("assignment_id", UUID(as_uuid=True),
                  sa.ForeignKey("ps_assignments.id", name="fk_ps_next_actions_assignment_id"),
                  nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("owner_user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", name="fk_ps_next_actions_owner_user_id_users"),
                  nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ps_next_actions_company_id", "ps_next_actions", ["company_id"])
    op.create_index("ix_ps_next_actions_assignment_id", "ps_next_actions", ["assignment_id"])
    op.execute(_rls("ps_next_actions"))


def downgrade() -> None:
    op.drop_table("ps_next_actions")
    op.drop_table("ps_assignments")
    op.drop_table("ps_clients")
