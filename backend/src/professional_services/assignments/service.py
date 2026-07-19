import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped

from .models import STAGES, PSAssignment


class AssignmentError(Exception):
    def __init__(self, message_key: str, status: int = 409) -> None:
        self.message_key = message_key
        self.status = status


def create_assignment(
    db: Session, ctx: TenantContext, client_id: uuid.UUID, title: str,
    official_deadline_on: date | None, internal_target_on: date | None,
) -> PSAssignment:
    assignment = PSAssignment(
        company_id=ctx.company_id, client_id=client_id, title=title,
        official_deadline_on=official_deadline_on, internal_target_on=internal_target_on,
    )
    db.add(assignment)
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


def change_stage(db: Session, assignment: PSAssignment, to: str) -> PSAssignment:
    """The single entry point for stage changes (mirrors service_orders'
    change_status chokepoint — one hardcoded, linear stage list here, not a
    configurable matrix)."""
    if to not in STAGES:
        raise AssignmentError("errors.ps.invalid_stage", status=400)
    assignment.stage = to
    if to == "delivered":
        assignment.lifecycle_state = "delivered"
    db.commit()
    return assignment
