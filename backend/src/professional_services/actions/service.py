import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped

from .models import PSNextAction

# Hardcoded for this slice — PS's real per-tenant configurable thresholds
# (threshold_attention/threshold_urgent) are out of scope.
ATTENTION_WINDOW = timedelta(days=2)


def compute_risk(due_on: date, completed: bool, today: date) -> str:
    """Pure, request-time risk classification — no persisted risk column, no
    background job, no notification. Literal result: "done" | "overdue" |
    "attention" | "ok"."""
    if completed:
        return "done"
    if due_on < today:
        return "overdue"
    if due_on <= today + ATTENTION_WINDOW:
        return "attention"
    return "ok"


def create_action(
    db: Session, ctx: TenantContext, assignment_id: uuid.UUID, title: str,
    owner_user_id: uuid.UUID, due_on: date,
) -> PSNextAction:
    action = PSNextAction(
        company_id=ctx.company_id, assignment_id=assignment_id, title=title,
        owner_user_id=owner_user_id, due_on=due_on,
    )
    db.add(action)
    db.commit()
    return action


def list_actions(
    db: Session, ctx: TenantContext, assignment_id: uuid.UUID | None = None
) -> list[PSNextAction]:
    stmt = scoped(select(PSNextAction), PSNextAction, ctx)
    if assignment_id is not None:
        stmt = stmt.where(PSNextAction.assignment_id == assignment_id)
    return list(db.scalars(stmt.order_by(PSNextAction.due_on)))


def get_action(db: Session, ctx: TenantContext, action_id: uuid.UUID) -> PSNextAction | None:
    stmt = scoped(select(PSNextAction), PSNextAction, ctx).where(PSNextAction.id == action_id)
    return db.scalar(stmt)


def complete_action(db: Session, action: PSNextAction) -> PSNextAction:
    action.completed_at = datetime.now(UTC)
    db.commit()
    return action
