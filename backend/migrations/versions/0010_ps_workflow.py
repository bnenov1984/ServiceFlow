"""Migration #10: Professional Services two-axis workflow model
(docs/business-os/17, modules/professional-services/docs 09/11/12,
ADR-PS-005). Replaces the walking skeleton's hardcoded single-stage-list
placeholder (migration 0007) with the real model: org-configurable
workflow templates with ordered, code-owned-category stages; assignments
get their own copied stage set at creation (copy-on-create — template
edits never affect existing assignments); an assignment's lifecycle state
(fixed, global) stays separate from its current business stage
(configurable, per-template); every stage change is recorded in an
append-only history table (same discipline as timeline_events, migration
0004).

No configurable deadline/risk engine, no notifications, no checklists —
deliberately out of scope for this slice.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

# Code-owned stage categories (ADR-PS-005): org-configurable stage *names*
# sit on top of these five fixed categories, which is what lets dashboards
# and inactivity rules stay deterministic across arbitrary custom vocabularies.
STAGE_CATEGORIES = ("work", "waiting_client", "waiting_documents", "review", "delivery")


def _rls(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);
"""


def upgrade() -> None:
    op.create_table(
        "ps_workflow_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_ps_workflow_templates_company_id_companies"),
                  nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ps_workflow_templates_company_id", "ps_workflow_templates",
                    ["company_id"])
    op.execute(_rls("ps_workflow_templates"))

    op.create_table(
        "ps_workflow_template_stages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_ps_workflow_template_stages_company_id_companies"),
                  nullable=False),
        sa.Column("template_id", UUID(as_uuid=True),
                  sa.ForeignKey("ps_workflow_templates.id",
                                name="fk_ps_workflow_template_stages_template_id"),
                  nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "category IN ('work', 'waiting_client', 'waiting_documents', 'review', 'delivery')",
            name="ck_ps_workflow_template_stages_category",
        ),
    )
    op.create_index("ix_ps_workflow_template_stages_company_id", "ps_workflow_template_stages",
                    ["company_id"])
    op.create_index("ix_ps_workflow_template_stages_template_id", "ps_workflow_template_stages",
                    ["template_id"])
    op.execute(_rls("ps_workflow_template_stages"))

    op.create_table(
        "ps_assignment_stages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_ps_assignment_stages_company_id_companies"),
                  nullable=False),
        sa.Column("assignment_id", UUID(as_uuid=True),
                  sa.ForeignKey("ps_assignments.id",
                                name="fk_ps_assignment_stages_assignment_id"),
                  nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "category IN ('work', 'waiting_client', 'waiting_documents', 'review', 'delivery')",
            name="ck_ps_assignment_stages_category",
        ),
    )
    op.create_index("ix_ps_assignment_stages_company_id", "ps_assignment_stages", ["company_id"])
    op.create_index("ix_ps_assignment_stages_assignment_id", "ps_assignment_stages",
                    ["assignment_id"])
    op.execute(_rls("ps_assignment_stages"))

    op.create_table(
        "ps_assignment_stage_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_ps_assignment_stage_history_company_id_companies"),
                  nullable=False),
        sa.Column("assignment_id", UUID(as_uuid=True),
                  sa.ForeignKey("ps_assignments.id",
                                name="fk_ps_assignment_stage_history_assignment_id"),
                  nullable=False),
        sa.Column("from_stage_id", UUID(as_uuid=True),
                  sa.ForeignKey("ps_assignment_stages.id",
                                name="fk_ps_assignment_stage_history_from_stage_id"),
                  nullable=True),
        sa.Column("to_stage_id", UUID(as_uuid=True),
                  sa.ForeignKey("ps_assignment_stages.id",
                                name="fk_ps_assignment_stage_history_to_stage_id"),
                  nullable=False),
        sa.Column("changed_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id",
                                name="fk_ps_assignment_stage_history_changed_by_users"),
                  nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ps_assignment_stage_history_company_id", "ps_assignment_stage_history",
                    ["company_id"])
    op.create_index("ix_ps_assignment_stage_history_assignment", "ps_assignment_stage_history",
                    ["assignment_id", "changed_at"])
    op.execute(_rls("ps_assignment_stage_history"))
    op.execute("""
CREATE FUNCTION ps_assignment_stage_history_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'ps_assignment_stage_history is append-only (PS-26 INV-10)';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER ps_assignment_stage_history_no_rewrite
    BEFORE UPDATE OR DELETE ON ps_assignment_stage_history
    FOR EACH ROW EXECUTE FUNCTION ps_assignment_stage_history_append_only();
""")

    # ps_assignments: replace the walking skeleton's hardcoded `stage` string
    # with a reference to the assignment's own copied stage, plus provenance
    # of the template it was copied from (PS-25). lifecycle_state gains
    # 'completed' (PS-11 §1) - the walking skeleton had only 3 of the 4
    # frozen states.
    op.drop_constraint("ck_ps_assignments_stage", "ps_assignments", type_="check")
    op.drop_column("ps_assignments", "stage")
    op.add_column(
        "ps_assignments",
        sa.Column("current_stage_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ps_assignments_current_stage_id", "ps_assignments", "ps_assignment_stages",
        ["current_stage_id"], ["id"],
    )
    op.add_column(
        "ps_assignments",
        sa.Column("workflow_template_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ps_assignments_workflow_template_id", "ps_assignments", "ps_workflow_templates",
        ["workflow_template_id"], ["id"],
    )
    op.drop_constraint("ck_ps_assignments_lifecycle_state", "ps_assignments", type_="check")
    op.create_check_constraint(
        "ck_ps_assignments_lifecycle_state", "ps_assignments",
        "lifecycle_state IN ('active', 'delivered', 'completed', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ps_assignments_lifecycle_state", "ps_assignments", type_="check")
    op.create_check_constraint(
        "ck_ps_assignments_lifecycle_state", "ps_assignments",
        "lifecycle_state IN ('active', 'delivered', 'cancelled')",
    )
    op.drop_constraint("fk_ps_assignments_workflow_template_id", "ps_assignments",
                      type_="foreignkey")
    op.drop_column("ps_assignments", "workflow_template_id")
    op.drop_constraint("fk_ps_assignments_current_stage_id", "ps_assignments",
                      type_="foreignkey")
    op.drop_column("ps_assignments", "current_stage_id")
    op.add_column(
        "ps_assignments",
        sa.Column("stage", sa.String(), nullable=False, server_default="intake"),
    )
    op.create_check_constraint(
        "ck_ps_assignments_stage", "ps_assignments",
        "stage IN ('intake', 'in_progress', 'waiting_client', 'delivered')",
    )

    op.execute("DROP TRIGGER ps_assignment_stage_history_no_rewrite "
              "ON ps_assignment_stage_history")
    op.execute("DROP FUNCTION ps_assignment_stage_history_append_only()")
    op.drop_table("ps_assignment_stage_history")
    op.drop_table("ps_assignment_stages")
    op.drop_table("ps_workflow_template_stages")
    op.drop_table("ps_workflow_templates")
