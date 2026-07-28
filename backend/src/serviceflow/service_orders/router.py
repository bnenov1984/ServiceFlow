"""Order endpoints per docs/09 §service orders. Mounted at /api/v1 (no blanket
prefix) since docs/09 places some resources flat (/part-lines/{id}) rather than
nested under /orders — matches the assets router's pattern."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from business_os.identity.contracts import get_company_profile
from business_os.identity.deps import (
    TenantDbDep,
    TenantDep,
    require_csrf,
    require_subscription_ok,
)
from serviceflow.assets import service as assets_service
from serviceflow.customers import service as customers_service
from serviceflow.service_orders import contracts as orders_contracts
from serviceflow.service_orders import lines, protocol, service, statuses
from serviceflow.service_orders.lines import PART_STATES
from serviceflow.service_orders.models import (
    AccessoryItem,
    Diagnosis,
    LaborLine,
    PartLine,
    ServiceOrder,
)
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


class OrderListItemOut(OrderOut):
    """GET /orders only — adds the joined display fields the Kanban/list board
    needs (docs/15 §6.3) without touching OrderOut's other callers."""
    customer_name: str
    asset_label: str
    status_changed_at: datetime | None
    overdue: bool


class DiagnosisOut(BaseModel):
    observed: str
    cause: str
    recommendation: str
    estimated_cost: float | None
    estimated_days: int | None
    repairable: bool | None
    approval_required: bool
    approval: dict[str, Any] | None

    @staticmethod
    def of(d: Diagnosis) -> "DiagnosisOut":
        return DiagnosisOut(
            observed=d.observed, cause=d.cause, recommendation=d.recommendation,
            estimated_cost=float(d.estimated_cost) if d.estimated_cost is not None else None,
            estimated_days=d.estimated_days, repairable=d.repairable,
            approval_required=d.approval_required, approval=d.approval,
        )


class DiagnosisIn(BaseModel):
    observed: str = Field(default="", max_length=5000)
    cause: str = Field(default="", max_length=5000)
    recommendation: str = Field(default="", max_length=5000)
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    estimated_days: int | None = Field(default=None, ge=0)
    repairable: bool | None = None
    approval_required: bool = False


class PartLineOut(BaseModel):
    id: uuid.UUID
    name: str
    qty: int
    unit_cost: float
    unit_price: float
    state: str

    @staticmethod
    def of(p: PartLine) -> "PartLineOut":
        return PartLineOut(id=p.id, name=p.name, qty=p.qty,
                           unit_cost=float(p.unit_cost), unit_price=float(p.unit_price),
                           state=p.state)


class PartLineIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    qty: int = Field(default=1, ge=1)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)


class PartLinePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    qty: int | None = Field(default=None, ge=1)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    state: str | None = None


class LaborLineOut(BaseModel):
    id: uuid.UUID
    description: str
    qty: int
    unit_price: float
    duration_min: int | None
    performed_by: uuid.UUID | None

    @staticmethod
    def of(line: LaborLine) -> "LaborLineOut":
        return LaborLineOut(id=line.id, description=line.description, qty=line.qty,
                            unit_price=float(line.unit_price),
                            duration_min=line.duration_min, performed_by=line.performed_by)


class LaborLineIn(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    qty: int = Field(default=1, ge=1)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    duration_min: int | None = Field(default=None, ge=0)
    performed_by: uuid.UUID | None = None


class LaborLinePatch(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=500)
    qty: int | None = Field(default=None, ge=1)
    unit_price: Decimal | None = Field(default=None, ge=0)
    duration_min: int | None = Field(default=None, ge=0)


class AccessoryOut(BaseModel):
    id: uuid.UUID
    name: str
    qty: int
    returned: bool

    @staticmethod
    def of(a: AccessoryItem) -> "AccessoryOut":
        return AccessoryOut(id=a.id, name=a.name, qty=a.qty, returned=a.returned)


class AccessoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    qty: int = Field(default=1, ge=1)


class AccessoryPatch(BaseModel):
    returned: bool


class OrderDetailOut(OrderOut):
    """The docs/09 'full detail' shape — aggregate members only (docs/01 §4);
    tasks/attachments/contacts/timeline are outside the aggregate, fetched
    separately."""

    diagnosis: DiagnosisOut | None
    part_lines: list[PartLineOut]
    labor_lines: list[LaborLineOut]
    accessories: list[AccessoryOut]
    estimated_total: float
    paid_amount: float
    balance: float


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


@router.get("/orders")
def list_orders(db: TenantDbDep, tenant: TenantDep, state: str = "open",
                status_code: str | None = None, technician_id: uuid.UUID | None = None,
                customer_id: uuid.UUID | None = None,
                priority: str | None = None, overdue: bool = False,
                include_archived: bool = False) -> list[OrderListItemOut]:
    orders = service.list_orders(
        db, tenant, state=state, status_code=status_code, technician_id=technician_id,
        customer_id=customer_id, priority=priority, overdue=overdue,
        include_archived=include_archived,
    )
    customers = customers_service.get_many(db, tenant, (o.customer_id for o in orders))
    assets = assets_service.get_many(db, tenant, (o.asset_id for o in orders))
    today = datetime.now(UTC).date()
    return [
        OrderListItemOut(
            **OrderOut.of(o).model_dump(),
            customer_name=customers[o.customer_id].name if o.customer_id in customers else "",
            asset_label=assets[o.asset_id].label if o.asset_id in assets else "",
            status_changed_at=o.status_changed_at,
            overdue=statuses.is_overdue(o.status_code, o.promised_on, today),
        )
        for o in orders
    ]


@router.post("/orders",
            dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
            status_code=201)
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


@router.get("/orders/{order_id}")
def get_order(order_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> OrderDetailOut:
    order = _get_or_404(db, tenant, order_id)
    diagnosis = service.get_diagnosis(db, tenant, order_id)
    base = OrderOut.of(order)
    payment_summary = orders_contracts.get_payment_summary(db, tenant, order_id)
    return OrderDetailOut(
        **base.model_dump(),
        diagnosis=DiagnosisOut.of(diagnosis) if diagnosis else None,
        part_lines=[PartLineOut.of(p) for p in lines.list_part_lines(db, tenant, order_id)],
        labor_lines=[LaborLineOut.of(line)
                    for line in lines.list_labor_lines(db, tenant, order_id)],
        accessories=[AccessoryOut.of(a) for a in lines.list_accessories(db, tenant, order_id)],
        estimated_total=float(lines.order_totals(db, tenant, order_id)),
        paid_amount=float(payment_summary.paid_amount),
        balance=float(payment_summary.balance),
    )


@router.patch("/orders/{order_id}",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
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


@router.post("/orders/{order_id}/status",
            dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
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


@router.post("/orders/{order_id}/unlock",
            dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def unlock_order(order_id: uuid.UUID, body: UnlockRequest, db: TenantDbDep,
                 tenant: TenantDep) -> OrderOut:
    order = _get_or_404(db, tenant, order_id)
    try:
        return OrderOut.of(service.unlock(db, tenant, order, body.reason))
    except service.OrderError as e:
        raise _err(e) from e


@router.post("/orders/{order_id}/warranty-return",
            dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
            status_code=201)
def warranty_return(order_id: uuid.UUID, body: WarrantyReturnRequest, db: TenantDbDep,
                    tenant: TenantDep) -> OrderOut:
    order = _get_or_404(db, tenant, order_id)
    try:
        return OrderOut.of(service.warranty_return(db, tenant, order, body.complaint))
    except service.OrderError as e:
        raise _err(e) from e


@router.post("/orders/{order_id}/archive",
            dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def archive_order(order_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> OrderOut:
    order = _get_or_404(db, tenant, order_id)
    try:
        service.archive(db, tenant, order)
    except service.OrderError as e:
        raise _err(e) from e
    return OrderOut.of(order)


@router.get("/orders/{order_id}/timeline")
def order_timeline(order_id: uuid.UUID, db: TenantDbDep,
                   tenant: TenantDep) -> list[TimelineEventOut]:
    _get_or_404(db, tenant, order_id)
    return [
        TimelineEventOut(event_type=e.event_type, actor_user_id=e.actor_user_id,
                         data=e.data, created_at=e.created_at)
        for e in timeline_service.for_order(db, tenant, order_id)
    ]


# --- Diagnosis (0..1 per order, edited in place — docs/01 §Diagnosis) ---------

@router.put("/orders/{order_id}/diagnosis",
           dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def put_diagnosis(order_id: uuid.UUID, body: DiagnosisIn, db: TenantDbDep,
                  tenant: TenantDep) -> DiagnosisOut:
    order = _get_or_404(db, tenant, order_id)
    diagnosis = service.put_diagnosis(db, tenant, order, body.model_dump())
    return DiagnosisOut.of(diagnosis)


# --- Part lines ----------------------------------------------------------

@router.get("/orders/{order_id}/part-lines")
def list_part_lines(order_id: uuid.UUID, db: TenantDbDep,
                    tenant: TenantDep) -> list[PartLineOut]:
    _get_or_404(db, tenant, order_id)
    return [PartLineOut.of(p) for p in lines.list_part_lines(db, tenant, order_id)]


@router.post("/orders/{order_id}/part-lines",
            dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
            status_code=201)
def add_part_line(order_id: uuid.UUID, body: PartLineIn, db: TenantDbDep,
                  tenant: TenantDep) -> PartLineOut:
    order = _get_or_404(db, tenant, order_id)
    line = lines.add_part_line(db, tenant, order, name=body.name, qty=body.qty,
                               unit_cost=body.unit_cost, unit_price=body.unit_price)
    return PartLineOut.of(line)


@router.patch("/part-lines/{line_id}",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def patch_part_line(line_id: uuid.UUID, body: PartLinePatch, db: TenantDbDep,
                    tenant: TenantDep) -> PartLineOut:
    line = lines.get_part_line(db, tenant, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.part_lines.not_found", "params": {},
        })
    if body.state is not None and body.state not in PART_STATES:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_state", "message_key": "errors.part_lines.invalid_state",
            "params": {},
        })
    line = lines.update_part_line(db, tenant, line, body.model_dump(exclude_unset=True))
    return PartLineOut.of(line)


# --- Labor lines -----------------------------------------------------------

@router.get("/orders/{order_id}/labor-lines")
def list_labor_lines(order_id: uuid.UUID, db: TenantDbDep,
                     tenant: TenantDep) -> list[LaborLineOut]:
    _get_or_404(db, tenant, order_id)
    return [LaborLineOut.of(line) for line in lines.list_labor_lines(db, tenant, order_id)]


@router.post("/orders/{order_id}/labor-lines",
            dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
            status_code=201)
def add_labor_line(order_id: uuid.UUID, body: LaborLineIn, db: TenantDbDep,
                   tenant: TenantDep) -> LaborLineOut:
    order = _get_or_404(db, tenant, order_id)
    line = lines.add_labor_line(db, tenant, order, description=body.description,
                                qty=body.qty, unit_price=body.unit_price,
                                duration_min=body.duration_min,
                                performed_by=body.performed_by)
    return LaborLineOut.of(line)


@router.patch("/labor-lines/{line_id}",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def patch_labor_line(line_id: uuid.UUID, body: LaborLinePatch, db: TenantDbDep,
                     tenant: TenantDep) -> LaborLineOut:
    line = lines.get_labor_line(db, tenant, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.labor_lines.not_found", "params": {},
        })
    line = lines.update_labor_line(db, tenant, line, body.model_dump(exclude_unset=True))
    return LaborLineOut.of(line)


# --- Accessories -------------------------------------------------------------

@router.get("/orders/{order_id}/accessories")
def list_accessories(order_id: uuid.UUID, db: TenantDbDep,
                     tenant: TenantDep) -> list[AccessoryOut]:
    _get_or_404(db, tenant, order_id)
    return [AccessoryOut.of(a) for a in lines.list_accessories(db, tenant, order_id)]


@router.post("/orders/{order_id}/accessories",
            dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
            status_code=201)
def add_accessory(order_id: uuid.UUID, body: AccessoryIn, db: TenantDbDep,
                  tenant: TenantDep) -> AccessoryOut:
    order = _get_or_404(db, tenant, order_id)
    item = lines.add_accessory(db, tenant, order, name=body.name, qty=body.qty)
    return AccessoryOut.of(item)


@router.patch("/accessories/{item_id}",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def patch_accessory(item_id: uuid.UUID, body: AccessoryPatch, db: TenantDbDep,
                    tenant: TenantDep) -> AccessoryOut:
    item = lines.get_accessory(db, tenant, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.accessories.not_found", "params": {},
        })
    item = lines.mark_accessory_returned(db, tenant, item, body.returned)
    return AccessoryOut.of(item)


# --- Protocol (приемо-предавателен протокол) --------------------------------
# Минимален intake variant only (docs/13 Етап-2 scope note); the delivery
# variant and extended fields (estimate, warranty, terms) are Етап 4.

@router.get("/orders/{order_id}/protocol.pdf")
def order_protocol(order_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep,
                   type: str = "intake") -> Response:  # param name matches docs/09 ?type=
    if type == "delivery":
        raise HTTPException(status_code=501, detail={
            "code": "not_implemented", "message_key": "errors.protocol.delivery_not_available",
            "params": {},
        })
    if type != "intake":
        raise HTTPException(status_code=400, detail={
            "code": "invalid_type", "message_key": "errors.protocol.invalid_type", "params": {},
        })

    order = _get_or_404(db, tenant, order_id)
    customer = customers_service.get(db, tenant, order.customer_id)
    asset = assets_service.get(db, tenant, order.asset_id)
    if customer is None or asset is None:
        raise _not_found()
    asset_type = assets_service.get_type_by_id(db, tenant, asset.asset_type_id)
    company = get_company_profile(db, tenant.company_id)
    assert asset_type is not None

    identifiers = [
        (fd["label_bg"], str(asset.field_values[fd["key"]]))
        for fd in asset_type.field_defs
        if fd.get("identifier_kind") and asset.field_values.get(fd["key"])
    ]
    accessory_names = [
        f"{a.name} x{a.qty}" if a.qty > 1 else a.name
        for a in lines.list_accessories(db, tenant, order_id)
    ]
    requisites = company.requisites or {}

    pdf_bytes = protocol.generate_intake_protocol(protocol.ProtocolData(
        company_name=company.name,
        company_address=str(requisites.get("address", "")),
        company_phone=str(requisites.get("phone", "")),
        order_number=order.number,
        created_on=order.created_at.date(),
        customer_name=customer.name,
        customer_phone=customer.phone,
        asset_type_name=asset_type.name_bg,
        asset_label=asset.label,
        asset_identifiers=identifiers,
        complaint=order.complaint,
        accessories=accessory_names,
    ))
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="protokol-{order.number}.pdf"'},
    )
