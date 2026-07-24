import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from professional_services.catalog.service import CatalogError, list_template_stages

from .models import PSAssignment, PSAssignmentStage, PSAssignmentStageHistory


class AssignmentError(Exception):
    def __init__(self, message_key: str, status: int = 409) -> None:
        self.message_key = message_key
        self.status = status


def create_assignment(
    db: Session, ctx: TenantContext, client_id: uuid.UUID, title: str,
    official_deadline_on: date | None, internal_target_on: date | None,
    workflow_template_id: uuid.UUID | None = None,
) -> PSAssignment:
    """Copy-on-create (PS-12 §5): if a workflow template is given, its stages
    are copied onto this assignment's own PSAssignmentStage rows right now.
    A later edit to the template never touches this copy — the assignment
    owns it from this point on."""
    assignment = PSAssignment(
        company_id=ctx.company_id, client_id=client_id, title=title,
        official_deadline_on=official_deadline_on, internal_target_on=internal_target_on,
        workflow_template_id=workflow_template_id,
    )
    db.add(assignment)
    db.flush()

    if workflow_template_id is not None:
        template_stages = list_template_stages(db, ctx, workflow_template_id)
        if not template_stages:
            raise CatalogError("errors.ps.template_needs_stages")
        first_stage: PSAssignmentStage | None = None
        for stage in template_stages:
            copy = PSAssignmentStage(
                company_id=ctx.company_id, assignment_id=assignment.id,
                name=stage.name, category=stage.category, sort=stage.sort,
            )
            db.add(copy)
            db.flush()
            if first_stage is None:
                first_stage = copy
        assignment.current_stage_id = first_stage.id if first_stage else None

    db.commit()
    return assignment


def list_assignments(db: Session, ctx: TenantContext) -> list[PSAssignment]:
    stmt = scoped(select(PSAssignment), PSAssignment, ctx).order_by(
        PSAssignment.created_at.desc()
    )
    return list(db.scalars(stmt))


def get_assignment(
    db: Session, ctx: TenantContext, assignment_id: uuid.UUID
) -> PSAssignment | None:
    stmt = scoped(select(PSAssignment), PSAssignment, ctx).where(
        PSAssignment.id == assignment_id
    )
    return db.scalar(stmt)


def list_assignment_stages(
    db: Session, ctx: TenantContext, assignment_id: uuid.UUID
) -> list[PSAssignmentStage]:
    stmt = scoped(select(PSAssignmentStage), PSAssignmentStage, ctx).where(
        PSAssignmentStage.assignment_id == assignment_id
    ).order_by(PSAssignmentStage.sort)
    return list(db.scalars(stmt))


def get_assignment_stage(
    db: Session, ctx: TenantContext, assignment_id: uuid.UUID, stage_id: uuid.UUID
) -> PSAssignmentStage | None:
    stmt = scoped(select(PSAssignmentStage), PSAssignmentStage, ctx).where(
        PSAssignmentStage.assignment_id == assignment_id, PSAssignmentStage.id == stage_id
    )
    return db.scalar(stmt)


def change_stage(
    db: Session, ctx: TenantContext, assignment: PSAssignment, to_stage_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> PSAssignment:
    """The single entry point for stage changes (PS-12 §4: any of the
    assignment's own copied stages is a valid target — free-form, no
    per-template transition matrix). Every change is recorded in the
    append-only ps_assignment_stage_history (PS-26 INV-10) in the same
    transaction, so history can never diverge from state.

    Not routed through the shared domain-event bus: that bus's sole
    consumer today (serviceflow.timeline) filters only on "is subject_id
    present", not on event type, and would try to write
    TimelineEvent.order_id (FK'd to service_orders) from a ps_assignments
    id — a foreign-key violation waiting to happen. Recorded as a
    follow-up prerequisite, not fixed here (out of this slice's scope).
    """
    target = get_assignment_stage(db, ctx, assignment.id, to_stage_id)
    if target is None:
        raise AssignmentError("errors.ps.invalid_stage", status=400)
    if target.id == assignment.current_stage_id:
        raise AssignmentError("errors.ps.stage_unchanged", status=400)

    db.add(PSAssignmentStageHistory(
        company_id=ctx.company_id, assignment_id=assignment.id,
        from_stage_id=assignment.current_stage_id, to_stage_id=target.id,
        changed_by=actor_user_id,
    ))
    assignment.current_stage_id = target.id
    if target.category == "delivery":
        assignment.lifecycle_state = "delivered"
    db.commit()
    return assignment
