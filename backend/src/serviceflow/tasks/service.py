"""Task operations. Completion never auto-changes order status (docs/01 §Task —
V1 rule: humans move orders); completion on an order-bound task is timelined."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.events import DomainEvent, publish
from serviceflow.service_orders import statuses
from serviceflow.service_orders.models import ServiceOrder
from serviceflow.tasks.models import Task


class TaskError(Exception):
    def __init__(self, message_key: str, status: int = 409) -> None:
        self.message_key = message_key
        self.status = status


def _now() -> datetime:
    return datetime.now(UTC)


def create(db: Session, ctx: TenantContext, *, title: str,
           order_id: uuid.UUID | None = None, assignee_id: uuid.UUID | None = None,
           due_on: date | None = None, note: str = "", is_call: bool = False) -> Task:
    task = Task(company_id=ctx.company_id, order_id=order_id, title=title,
               assignee_id=assignee_id, due_on=due_on, note=note, is_call=is_call,
               created_by=ctx.user_id)
    db.add(task)
    db.flush()
    if order_id is not None:
        publish(db, DomainEvent(type="task_created", company_id=ctx.company_id,
                                actor_user_id=ctx.user_id, subject_id=order_id,
                                data={"title": title}))
    db.commit()
    return task


def get(db: Session, ctx: TenantContext, task_id: uuid.UUID) -> Task | None:
    return db.scalar(scoped(select(Task), Task, ctx).where(Task.id == task_id))


def list_for_order(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> list[Task]:
    return list(db.scalars(
        scoped(select(Task), Task, ctx).where(Task.order_id == order_id)
        .order_by(Task.created_at)
    ))


def list_tasks(db: Session, ctx: TenantContext, *, today: bool = False,
              mine: bool = False, calls: bool = False) -> list[Task]:
    stmt = scoped(select(Task), Task, ctx).where(Task.is_done.is_(False))
    if today:
        stmt = stmt.where(Task.due_on.is_not(None), Task.due_on <= _now().date())
    if mine:
        stmt = stmt.where(Task.assignee_id == ctx.user_id)
    if calls:
        stmt = stmt.where(Task.is_call.is_(True))
    return list(db.scalars(stmt.order_by(Task.due_on.asc().nulls_last())))


def _order_is_terminal(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> bool:
    order = db.scalar(
        scoped(select(ServiceOrder), ServiceOrder, ctx).where(ServiceOrder.id == order_id)
    )
    return order is not None and order.status_code in statuses.TERMINAL


def complete(db: Session, ctx: TenantContext, task: Task) -> Task:
    task.is_done = True
    task.completed_by = ctx.user_id
    task.completed_at = _now()
    if task.order_id is not None:
        publish(db, DomainEvent(type="task_completed", company_id=ctx.company_id,
                                actor_user_id=ctx.user_id, subject_id=task.order_id,
                                data={"title": task.title}))
    db.commit()
    return task


def reopen(db: Session, ctx: TenantContext, task: Task) -> Task:
    if task.order_id is not None and _order_is_terminal(db, ctx, task.order_id):
        raise TaskError("errors.tasks.order_terminal")
    task.is_done = False
    task.completed_by = None
    task.completed_at = None
    if task.order_id is not None:
        publish(db, DomainEvent(type="task_reopened", company_id=ctx.company_id,
                                actor_user_id=ctx.user_id, subject_id=task.order_id,
                                data={"title": task.title}))
    db.commit()
    return task


def reassign(db: Session, ctx: TenantContext, task: Task,
            assignee_id: uuid.UUID | None) -> Task:
    task.assignee_id = assignee_id
    db.commit()
    return task
