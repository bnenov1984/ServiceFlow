"""PSAssignment and its two-axis workflow model (ADR-PS-005, migration 0010).

Two independent axes, on purpose:
- `lifecycle_state`: fixed, code-owned, identical for every organisation
  (PS-11). Invariants and permissions hang here.
- `current_stage_id`: the assignment's own copy of one workflow template's
  stages (`PSAssignmentStage`), org-configurable vocabulary. Copied at
  creation (copy-on-create) so a later template edit never mutates an
  in-flight assignment (PS-12 §5).

`PSAssignmentStageHistory` is append-only (DB trigger, migration 0010) —
same discipline as ServiceFlow's timeline_events (migration 0004): the
history of who moved what, when, is never editable by the application.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id

LIFECYCLE_STATES = ("active", "delivered", "completed", "cancelled")


class PSAssignment(Base, TimestampMixin):
    __tablename__ = "ps_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ps_clients.id"), index=True)
    title: Mapped[str]
    lifecycle_state: Mapped[str] = mapped_column(default="active")
    workflow_template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ps_workflow_templates.id"), default=None
    )
    current_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ps_assignment_stages.id"), default=None
    )
    official_deadline_on: Mapped[date | None] = mapped_column(default=None)
    internal_target_on: Mapped[date | None] = mapped_column(default=None)


class PSAssignmentStage(Base, TimestampMixin):
    """The assignment's own copied stage — an instance, not a template
    reference (PS-09 §3.1: "stage copies, not template references")."""

    __tablename__ = "ps_assignment_stages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ps_assignments.id"), index=True
    )
    name: Mapped[str]
    category: Mapped[str]
    sort: Mapped[int]


class PSAssignmentStageHistory(Base):
    """Append-only (DB trigger, migration 0010): every stage change, forever."""

    __tablename__ = "ps_assignment_stage_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ps_assignments.id"), index=True
    )
    from_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ps_assignment_stages.id"), default=None
    )
    to_stage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ps_assignment_stages.id"))
    changed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())
