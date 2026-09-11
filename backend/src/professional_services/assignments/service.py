import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from professional_services.catalog.service import CatalogError, list_template_stages

from . import risk
from .models import (
    PSAssignment,
    PSAssignmentStage,
    PSAssignmentStageHistory,
    PSDeadlineChange,
)


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

    recompute_risk(assignment)
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

    Not routed through the shared domain-event bus: serviceflow.timeline's
    subscriber now gates on an explicit ServiceFlow-only type allowlist
    (BOS-09 Q8, resolved) so publishing here would simply be ignored
    rather than crash — but this module has no subscriber of its own yet,
    so the history row is still written directly, in the same transaction.
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
    db.flush()  # so updated_at (this function's "activity" proxy) is fresh before recompute
    recompute_risk(assignment)
    db.commit()
    return assignment


def _last_activity_on(assignment: PSAssignment) -> date:
    """Minimal-footprint stand-in for PS-25's full `last_activity_at`
    (derived from an activity-event log this slice does not build): reuses
    `updated_at`, which already ticks on every mutation of the assignment
    row (TimestampMixin's `onupdate=func.now()`), including stage changes
    and deadline changes. Coarser than the eventual design, still
    deterministic and truthful about "the last time this row changed"."""
    return assignment.updated_at.date()


def recompute_risk(assignment: PSAssignment, today: date | None = None) -> bool:
    """Recomputes current_deadline_risk/current_stale from the assignment's
    own stored fields (INV-9: reproducible from stored data + today, never
    itself authoritative) and persists only if either value actually
    changed. Returns whether anything changed - the idempotence contract
    the background job (evaluate_company_risk) relies on: re-running with
    no underlying change must be a true no-op, including at the database
    level (no dirty row, no `updated_at` tick).

    Defaults to the UTC calendar date, matching actions.service.compute_risk
    - the two risk engines must agree on what "today" means, or the same
    moment near local midnight can read as "overdue" from one and not the
    other purely depending on the caller's OS timezone."""
    today = today or datetime.now(UTC).date()
    new_risk = risk.deadline_risk(assignment.official_deadline_on, assignment.lifecycle_state,
                                  today)
    new_stale = risk.is_stale(_last_activity_on(assignment), assignment.lifecycle_state, today)
    changed = new_risk != assignment.current_deadline_risk or new_stale != assignment.current_stale
    if changed:
        assignment.current_deadline_risk = new_risk
        assignment.current_stale = new_stale
    return changed


def change_deadline(
    db: Session, ctx: TenantContext, assignment: PSAssignment, new_deadline_on: date,
    reason: str, actor_user_id: uuid.UUID | None, today: date | None = None,
) -> PSAssignment:
    """The reasoned-change chokepoint for the official deadline (ADR-PS-008
    §5): a mandatory reason, an append-only history row, then the field
    itself changes - never the other way, and never a direct field write
    anywhere else. Recomputes risk immediately in the same transaction
    (the "on-write recompute" half of PS-13 §7's two evaluation paths; the
    "morning job" half is evaluate_company_risk below)."""
    if not reason.strip():
        raise AssignmentError("errors.ps.deadline_reason_required", status=400)

    db.add(PSDeadlineChange(
        company_id=ctx.company_id, assignment_id=assignment.id,
        field="official_deadline_on", old_value=assignment.official_deadline_on,
        new_value=new_deadline_on, reason=reason.strip(), changed_by=actor_user_id,
    ))
    assignment.official_deadline_on = new_deadline_on
    db.flush()  # so updated_at (this function's "activity" proxy) is fresh before recompute
    recompute_risk(assignment, today)
    db.commit()
    return assignment


def list_deadline_changes(
    db: Session, ctx: TenantContext, assignment_id: uuid.UUID
) -> list[PSDeadlineChange]:
    stmt = scoped(select(PSDeadlineChange), PSDeadlineChange, ctx).where(
        PSDeadlineChange.assignment_id == assignment_id
    ).order_by(PSDeadlineChange.changed_at.desc())
    return list(db.scalars(stmt))


def evaluate_company_risk(db: Session, ctx: TenantContext, today: date | None = None) -> int:
    """The "morning per-tenant job" (PS-13 §7) as a plain, callable,
    idempotent function - not wired to any scheduler. No `jobs` table
    (ADR-006) exists yet anywhere in this codebase to schedule it from;
    building that platform-level infrastructure is out of this slice's
    scope. This function is what such a job would call once one exists;
    until then it is invoked on demand (see the /evaluate-risk endpoint).

    Only active assignments carry a live risk stream (risk.deadline_risk/
    is_stale both return the "off" value otherwise), so only those rows
    can possibly change here. Writes happen only where recompute_risk
    reports an actual change - idempotent by construction."""
    today = today or datetime.now(UTC).date()
    stmt = scoped(select(PSAssignment), PSAssignment, ctx).where(
        PSAssignment.lifecycle_state == "active"
    )
    changed_count = 0
    for assignment in db.scalars(stmt):
        if recompute_risk(assignment, today):
            changed_count += 1
    db.commit()
    return changed_count
