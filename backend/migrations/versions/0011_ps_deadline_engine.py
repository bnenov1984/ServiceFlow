"""Migration #11: Professional Services deadline/staleness engine slice
(docs/business-os/17, modules/professional-services/docs 13, ADR-PS-008).

Adds append-only ps_deadline_changes (PS-26 INV-11: official-deadline edits
only through a reasoned-change chokepoint, every change historised) and two
persisted-result columns on ps_assignments: current_deadline_risk and
current_stale. Both are written only by the deterministic engine
(professional_services.assignments.risk + service.recompute_risk) - never
user-editable, matching INV-9 (every risk output reproducible from stored
data + today, never itself a source of truth).

No notifications, no service types, no configurable thresholds/org
settings, no checklists - deliberately out of scope for this slice.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0011"
down_revision = "0010"
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
        "ps_deadline_changes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_ps_deadline_changes_company_id_companies"),
                  nullable=False),
        sa.Column("assignment_id", UUID(as_uuid=True),
                  sa.ForeignKey("ps_assignments.id",
                                name="fk_ps_deadline_changes_assignment_id"),
                  nullable=False),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("old_value", sa.Date(), nullable=True),
        sa.Column("new_value", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("changed_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id",
                                name="fk_ps_deadline_changes_changed_by_users"),
                  nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ps_deadline_changes_company_id", "ps_deadline_changes", ["company_id"])
    op.create_index("ix_ps_deadline_changes_assignment", "ps_deadline_changes",
                    ["assignment_id", "changed_at"])
    op.execute(_rls("ps_deadline_changes"))
    op.execute("""
CREATE FUNCTION ps_deadline_changes_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'ps_deadline_changes is append-only (PS-26 INV-11)';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER ps_deadline_changes_no_rewrite
    BEFORE UPDATE OR DELETE ON ps_deadline_changes
    FOR EACH ROW EXECUTE FUNCTION ps_deadline_changes_append_only();
""")

    op.add_column(
        "ps_assignments",
        sa.Column("current_deadline_risk", sa.String(), nullable=False, server_default="none"),
    )
    op.add_column(
        "ps_assignments",
        sa.Column("current_stale", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("ps_assignments", "current_stale")
    op.drop_column("ps_assignments", "current_deadline_risk")

    op.execute("DROP TRIGGER ps_deadline_changes_no_rewrite ON ps_deadline_changes")
    op.execute("DROP FUNCTION ps_deadline_changes_append_only()")
    op.drop_table("ps_deadline_changes")
