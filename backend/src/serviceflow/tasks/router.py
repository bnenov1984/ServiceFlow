"""Task endpoints per docs/09: order-nested create + cross-order views."""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from business_os.identity.deps import (
    TenantDbDep,
    TenantDep,
    require_csrf,
    require_subscription_ok,
)
from serviceflow.service_orders import service as orders_service
from serviceflow.tasks import service
from serviceflow.tasks.models import Task

router = APIRouter()


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    assignee_id: uuid.UUID | None = None
    due_on: date | None = None
    note: str = Field(default="", max_length=2000)
    is_call: bool = False


class TaskPatch(BaseModel):
    is_done: bool | None = None
    assignee_id: uuid.UUID | None = None
    assign: bool = False  # explicit flag: assignee_id=None may mean "unassign"
    due_on: date | None = None
    note: str | None = Field(default=None, max_length=2000)


class TaskOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID | None
    title: str
    is_done: bool
    assignee_id: uuid.UUID | None
    due_on: date | None
    note: str
    is_call: bool
    completed_by: uuid.UUID | None
    completed_at: datetime | None

    @staticmethod
    def of(t: Task) -> "TaskOut":
        return TaskOut(
            id=t.id, order_id=t.order_id, title=t.title, is_done=t.is_done,
            assignee_id=t.assignee_id, due_on=t.due_on, note=t.note, is_call=t.is_call,
            completed_by=t.completed_by, completed_at=t.completed_at,
        )


def _err(e: service.TaskError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": "task_error", "message_key": e.message_key, "params": {},
    })


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "code": "not_found", "message_key": "errors.tasks.not_found", "params": {},
    })


@router.get("/tasks")
def list_tasks(db: TenantDbDep, tenant: TenantDep, today: bool = False,
               mine: bool = False, calls: bool = False) -> list[TaskOut]:
    return [TaskOut.of(t) for t in service.list_tasks(db, tenant, today=today,
                                                       mine=mine, calls=calls)]


@router.post("/tasks", dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
            status_code=201)
def create_company_task(body: TaskIn, db: TenantDbDep, tenant: TenantDep) -> TaskOut:
    task = service.create(db, tenant, **body.model_dump())
    return TaskOut.of(task)


@router.get("/orders/{order_id}/tasks")
def list_order_tasks(order_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> list[TaskOut]:
    if orders_service.get(db, tenant, order_id) is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.orders.not_found", "params": {},
        })
    return [TaskOut.of(t) for t in service.list_for_order(db, tenant, order_id)]


@router.post("/orders/{order_id}/tasks",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
             status_code=201)
def create_order_task(order_id: uuid.UUID, body: TaskIn, db: TenantDbDep,
                      tenant: TenantDep) -> TaskOut:
    if orders_service.get(db, tenant, order_id) is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.orders.not_found", "params": {},
        })
    task = service.create(db, tenant, order_id=order_id, **body.model_dump())
    return TaskOut.of(task)


@router.patch("/tasks/{task_id}",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def patch_task(task_id: uuid.UUID, body: TaskPatch, db: TenantDbDep,
               tenant: TenantDep) -> TaskOut:
    task = service.get(db, tenant, task_id)
    if task is None:
        raise _not_found()
    try:
        if body.is_done is True and not task.is_done:
            task = service.complete(db, tenant, task)
        elif body.is_done is False and task.is_done:
            task = service.reopen(db, tenant, task)
        if body.assign:
            task = service.reassign(db, tenant, task, body.assignee_id)
        if body.due_on is not None or body.note is not None:
            if body.due_on is not None:
                task.due_on = body.due_on
            if body.note is not None:
                task.note = body.note
            db.commit()
    except service.TaskError as e:
        raise _err(e) from e
    return TaskOut.of(task)
