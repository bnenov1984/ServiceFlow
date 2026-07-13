"""Order endpoints per docs/09 §service orders."""

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from serviceflow.assets import service as assets_service
from serviceflow.customers import service as customers_service
from serviceflow.identity.deps import TenantDbDep, TenantDep, require_csrf
from serviceflow.service_orders import service, statuses
from serviceflow.service_orders.models import ServiceOrder
from serviceflow.timeline import service as timeline_service

router = APIRouter()


class OrderIn(BaseModel):
    customer_id: uuid.UUID
    asset_id: uuid.UUID
    complaint: str = Field(min_length=1, max_length=5000)
    priority: str = Field(default="normal", pattern="^(normal|high)$")
    promised_on: date | None = None
    technician_id: uuid.UUID | None = None


class OrderPatch(BaseModel):
    complaint: str | None = Field(default=None, min_length=1, max_length=5000)
    priority: str | None = Field(default=None, pattern="^(normal|high)$")
    promised_on: date | None = None
    warranty_days: int | None = Field(default=None, ge=0, le=3650)
    technician_id: uuid.UUID | None = None
    assign_technician: bool = False  # explicit flag: None may mean "unassign"


class StatusChange(BaseModel):
    to: str
    reason: str | None = Field(default=None, max_length=1000)
    approval: dict[str, Any] | None = None
    warranty_days: int | None = Field(default=None, ge=0, le=3650)


class UnlockRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class WarrantyReturnRequest(BaseModel):
    complaint: str = Field(min_length=1, max_length=5000)


class OrderOut(BaseModel):
    id: uuid.UUID
    number: str
    customer_id: uuid.UUID
    asset_id: uuid.UUID
    complaint: str
    status_code: str
    status_kind: str
    technician_id: uuid.UUID | None
    priority: str
    promised_on: date | None
    warranty_days: int | None
    origin_order_id: uuid.UUID | None
    delivered_at: datetime | None
    terminal_reason: str | None
    archived: bool
    row_version: int
    warning: str | None = None

    @staticmethod
    def of(o: ServiceOrder, warning: str | None = None) -> "OrderOut":
        return OrderOut(
            id=o.id, number=o.number, customer_id=o.customer_id, asset_id=o.asset_id,
            complaint=o.complaint, status_code=o.status_code,
            status_kind=statuses.kind_of(o.status_code).value,
            technician_id=o.technician_id, priority=o.priority,
            promised_on=o.promised_on, warranty_days=o.warranty_days,
            origin_order_id=o.origin_order_id, delivered_at=o.delivered_at,
            terminal_reason=o.terminal_reason, archived=o.archived_at is not None,
            row_version=o.row_version, warning=warning,
        )


class TimelineEventOut(BaseModel):
    event_type: str
    actor_user_id: uuid.UUID | None
    data: dict[str, Any]
    created_at: datetime


def _err(e: service.OrderError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": "order_error", "message_key": e.message_key, "params": {},
    })


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "code": "not_found", "message_key": "errors.orders.not_found", "params": {},
    })


def _get_or_404(db: TenantDbDep, tenant: TenantDep, order_id: uuid.UUID) -> ServiceOrder:
    order = service.get(db, tenant, order_id)
    if order is None:
        raise _not_found()
    return order


@router.get("")
def list_orders(db: TenantDbDep, tenant: TenantDep, state: str = "open",
                status_code: str | None = None, technician_id: uuid.UUID | None = None,
                priority: str | None = None, overdue: bool = False,
                include_archived: bool = False) -> list[OrderOut]:
    return [OrderOut.of(o) for o in service.list_orders(
        db, tenant, state=state, status_code=status_code, technician_id=technician_id,
        priority=priority, overdue=overdue, include_archived=include_archived,
    )]


@router.post("", dependencies=[Depends(require_csrf)], status_code=201)
def create_order(body: OrderIn, db: TenantDbDep, tenant: TenantDep) -> OrderOut:
    customer = customers_service.get(db, tenant, body.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.customers.not_found", "params": {},
        })
    asset = assets_service.get(db, tenant, body.asset_id)
    if asset is None or asset.customer_id != body.customer_id:
        raise HTTPException(status_code=400, detail={
            "code": "asset_mismatch", "message_key": "errors.orders.asset_mismatch",
            "params": {},
        })
    order = service.create(
        db, tenant, customer_id=body.customer_id, asset_id=body.asset_id,
        complaint=body.complaint, priority=body.priority,
        promised_on=body.promised_on, technician_id=body.technician_id,
    )
    return OrderOut.of(order)


@router.get("/{order_id}")
def get_order(order_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> OrderOut:
    return OrderOut.of(_get_or_404(db, tenant, order_id))


@router.patch("/{order_id}", dependencies=[Depends(require_csrf)])
def patch_order(order_id: uuid.UUID, body: OrderPatch, db: TenantDbDep,
                tenant: TenantDep) -> OrderOut:
    order = _get_or_404(db, tenant, order_id)
    if order.status_code in statuses.TERMINAL:
        raise HTTPException(status_code=409, detail={
            "code": "terminal", "message_key": "errors.orders.terminal_readonly",
            "params": {},
        })
    fields = body.model_dump(exclude_unset=True, exclude={"technician_id",
                                                          "assign_technician"})
    for key, value in fields.items():
        setattr(order, key, value)
    if body.assign_technician:
        service.assign_technician(db, tenant, order, body.technician_id)
    else:
        order.row_version += 1
    db.commit()
    return OrderOut.of(order)


@router.post("/{order_id}/status", dependencies=[Depends(require_csrf)])
def change_status(order_id: uuid.UUID, body: StatusChange, db: TenantDbDep,
                  tenant: TenantDep) -> OrderOut:
    order = _get_or_404(db, tenant, order_id)
    try:
        order, warning = service.change_status(
            db, tenant, order, to=body.to, reason=body.reason,
            approval=body.approval, warranty_days=body.warranty_days,
        )
    except service.OrderError as e:
        raise _err(e) from e
    return OrderOut.of(order, warning)


@router.post("/{order_id}/unlock", dependencies=[Depends(require_csrf)])
def unlock_order(order_id: uuid.UUID, body: UnlockRequest, db: TenantDbDep,
                 tenant: TenantDep) -> OrderOut:
    order = _get_or_404(db, tenant, order_id)
    try:
        return OrderOut.of(service.unlock(db, tenant, order, body.reason))
    except service.OrderError as e:
        raise _err(e) from e


@router.post("/{order_id}/warranty-return", dependencies=[Depends(require_csrf)],
             status_code=201)
def warranty_return(order_id: uuid.UUID, body: WarrantyReturnRequest, db: TenantDbDep,
                    tenant: TenantDep) -> OrderOut:
    order = _get_or_404(db, tenant, order_id)
    try:
        return OrderOut.of(service.warranty_return(db, tenant, order, body.complaint))
    except service.OrderError as e:
        raise _err(e) from e


@router.post("/{order_id}/archive", dependencies=[Depends(require_csrf)])
def archive_order(order_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> OrderOut:
    order = _get_or_404(db, tenant, order_id)
    try:
        service.archive(db, tenant, order)
    except service.OrderError as e:
        raise _err(e) from e
    return OrderOut.of(order)


@router.get("/{order_id}/timeline")
def order_timeline(order_id: uuid.UUID, db: TenantDbDep,
                   tenant: TenantDep) -> list[TimelineEventOut]:
    _get_or_404(db, tenant, order_id)
    return [
        TimelineEventOut(event_type=e.event_type, actor_user_id=e.actor_user_id,
                         data=e.data, created_at=e.created_at)
        for e in timeline_service.for_order(db, tenant, order_id)
    ]
