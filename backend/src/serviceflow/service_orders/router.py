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
    require_owner,
    require_repairflow_active,
    require_subscription_ok,
)
from serviceflow.assets import service as assets_service
from serviceflow.catalog import service as catalog_service
from serviceflow.catalog.models import CatalogItem
from serviceflow.customers import service as customers_service
from serviceflow.service_orders import contracts as orders_contracts
from serviceflow.service_orders import lines, protocol, service, statuses
from serviceflow.service_orders.lines import PART_STATES
from serviceflow.service_orders.models import (
    AccessoryItem,
    Diagnosis,
    LaborLine,
    OrderAdjustment,
    PartLine,
    ServiceOrder,
)
from serviceflow.timeline import service as timeline_service

router = APIRouter(dependencies=[Depends(require_repairflow_active)])


class DeliveryAddressIn(BaseModel):
    """Wave 5 Issue 12: same minimal shape as customers.router's
    CustomerDeliveryAddress — deliberately a separate, local definition
    rather than an import: an order's own copy of the address has no
    dependency on the customer contract's shape evolving independently."""

    address: str = Field(min_length=1, max_length=500)


class OrderIn(BaseModel):
    customer_id: uuid.UUID
    asset_id: uuid.UUID
    complaint: str = Field(min_length=1, max_length=5000)
    priority: str = Field(default="normal", pattern="^(normal|high)$")
    promised_on: date | None = None
    technician_id: uuid.UUID | None = None
    # Wave 3 Issues 21/26/27: captured at intake, accepted for any asset
    # type — fully optional for every profile (WP-D, Q9: reverses Cleanup
    # batch Issue 26's automotive-required rule). When lower than the
    # asset's previous maximum, `service.create()` rejects it unless the two
    # fields below are also given (Q10, Owner-only bypass).
    mileage: int | None = Field(default=None, ge=0)
    mileage_confirmed_lower: bool = False
    mileage_override_comment: str | None = Field(default=None, max_length=1000)
    # Wave 5 Issue 12: smallest order-level logistics model. No DB CHECK
    # (same precedent as `priority` above) — validated here only.
    delivery_method: str | None = Field(default=None, pattern="^(pickup|courier)$")
    delivery_address: DeliveryAddressIn | None = None


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
    completed_at: datetime | None
    terminal_reason: str | None
    archived: bool
    row_version: int
    mileage: int | None = None
    mileage_confirmed_lower: bool = False
    # Wave 5 Issue 12: independent copy taken at creation — never a live
    # reference back to the customer's own delivery_address.
    delivery_method: str | None = None
    delivery_address: DeliveryAddressIn | None = None
    # Wave 4 Issue 7: lets the client decide whether "Протокол за предаване"
    # can open the PDF directly or must show the unavailable message
    # up front, without a doomed round trip to a new tab.
    has_completion_snapshot: bool = False
    warning: str | None = None

    @staticmethod
    def of(o: ServiceOrder, warning: str | None = None) -> "OrderOut":
        delivery_address = (
            DeliveryAddressIn(address=o.delivery_address["address"])
            if o.delivery_address and o.delivery_address.get("address") else None
        )
        return OrderOut(
            id=o.id, number=o.number, customer_id=o.customer_id, asset_id=o.asset_id,
            complaint=o.complaint, status_code=o.status_code,
            status_kind=statuses.kind_of(o.status_code).value,
            technician_id=o.technician_id, priority=o.priority,
            promised_on=o.promised_on, warranty_days=o.warranty_days,
            delivery_method=o.delivery_method, delivery_address=delivery_address,
            origin_order_id=o.origin_order_id, completed_at=o.completed_at,
            terminal_reason=o.terminal_reason, archived=o.archived_at is not None,
            row_version=o.row_version, mileage=o.mileage,
            mileage_confirmed_lower=o.mileage_confirmed_lower,
            has_completion_snapshot=o.completion_snapshot is not None, warning=warning,
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
    catalog_item_id: uuid.UUID | None
    name: str
    code: str | None
    qty: int
    unit_cost: float
    unit_price: float
    state: str
    has_warranty: bool
    # order-workflow-revamp WP-J (Q5/Q5c): non-null only right after an add
    # or a state-changing PATCH, when a one-click status-change nudge
    # applies — never populated on a plain GET, and never itself a change;
    # the client still has to POST /orders/{id}/status to act on it.
    suggested_status: str | None = None

    @staticmethod
    def of(p: PartLine, suggested_status: str | None = None) -> "PartLineOut":
        return PartLineOut(id=p.id, catalog_item_id=p.catalog_item_id, name=p.name, code=p.code,
                           qty=p.qty, unit_cost=float(p.unit_cost), unit_price=float(p.unit_price),
                           state=p.state, has_warranty=p.has_warranty,
                           suggested_status=suggested_status)


class PartLineIn(BaseModel):
    """order-workflow-revamp WP-I (Q12a): a line is created only from a
    catalog item — no name/price field exists here at all. `catalog_item_id`
    is resolved against this order's company and `kind="part"` by the
    `add_part_line` endpoint below, which snapshots the item's current
    name/code/price onto the new row.

    WP-J (Q15b): `state` must be one of `lines.ADD_PART_STATES` (checked by
    the endpoint, not a pydantic Literal, for the same custom-400-with-
    message_key reason `patch_part_line` already validates `PartLinePatch.
    state` by hand) — the add form always sends one of its two buttons'
    explicit values; "issued" is only the default for callers that don't
    offer that choice (e.g. a fixture creating a line purely for an
    unrelated invoice/payment total)."""

    catalog_item_id: uuid.UUID
    qty: int = Field(default=1, ge=1)
    state: str = "issued"
    has_warranty: bool = True


class PartLinePatch(BaseModel):
    """No name/price field (Q12a: "no price/name field on order-line create
    or edit, for any role") — only what was never a catalog concern."""

    qty: int | None = Field(default=None, ge=1)
    has_warranty: bool | None = None
    state: str | None = None


class LaborLineOut(BaseModel):
    id: uuid.UUID
    catalog_item_id: uuid.UUID | None
    description: str
    code: str | None
    unit: str
    qty: float
    unit_price: float
    duration_min: int | None
    performed_by: uuid.UUID | None

    @staticmethod
    def of(line: LaborLine) -> "LaborLineOut":
        return LaborLineOut(
            id=line.id, catalog_item_id=line.catalog_item_id, description=line.description,
            code=line.code, unit=line.unit, qty=float(line.qty),
            unit_price=float(line.unit_price), duration_min=line.duration_min,
            performed_by=line.performed_by,
        )


class LaborLineIn(BaseModel):
    """Same catalog-only discipline as PartLineIn above. `duration_min`
    (Wave informational field, docs/01 §LaborLine) stays free entry — it was
    never a price/name field, just an optional "how long did it actually
    take" note."""

    catalog_item_id: uuid.UUID
    # Decimal, not int (ADR-BOS-013 §8): hours for an hourly item.
    qty: Decimal = Field(default=Decimal("1"), gt=0)
    duration_min: int | None = Field(default=None, ge=0)
    performed_by: uuid.UUID | None = None


class LaborLinePatch(BaseModel):
    qty: Decimal | None = Field(default=None, gt=0)
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


class AdjustmentOut(BaseModel):
    id: uuid.UUID
    amount: float
    reason: str
    created_by: uuid.UUID
    created_at: datetime

    @staticmethod
    def of(a: OrderAdjustment) -> "AdjustmentOut":
        return AdjustmentOut(id=a.id, amount=float(a.amount), reason=a.reason,
                             created_by=a.created_by, created_at=a.created_at)


class AdjustmentIn(BaseModel):
    amount: Decimal
    reason: str = Field(min_length=1, max_length=1000)


class OrderDetailOut(OrderOut):
    """The docs/09 'full detail' shape — aggregate members only (docs/01 §4);
    tasks/attachments/contacts/timeline are outside the aggregate, fetched
    separately."""

    diagnosis: DiagnosisOut | None
    part_lines: list[PartLineOut]
    labor_lines: list[LaborLineOut]
    accessories: list[AccessoryOut]
    adjustments: list[AdjustmentOut]
    estimated_total: float
    paid_amount: float
    balance: float


class ServiceHistoryEntryOut(BaseModel):
    """One visit in a vehicle's service history (Wave 3 Issues 21/26/27) —
    only data already naturally available from the order itself, no new
    aggregation. `customer_name` is the customer at THAT visit, which may
    differ from the asset's current owner after a transfer (Issue 20)."""

    order_id: uuid.UUID
    order_number: str
    created_at: datetime
    status_code: str
    customer_id: uuid.UUID
    customer_name: str
    complaint: str
    mileage: int | None


class OpenOrderOut(BaseModel):
    """Q6b: the asset-step pre-check backing „Има отворена поръчка №… →
    Отвори я" — read-only, mirrors customers' phone-check/eik-check and
    assets' reg-check shape. `service.create()`'s own
    `find_open_order_for_asset` call is what actually blocks a create; this
    is a convenience so the UI can show it before the user ever submits."""

    order_id: uuid.UUID | None = None
    number: str | None = None
    status_code: str | None = None


class AssetServiceHistoryOut(BaseModel):
    asset_id: uuid.UUID
    asset_label: str
    # Newest non-null order-level mileage; falls back to the legacy
    # Asset.field_values["mileage"] only when no order has recorded one yet.
    current_mileage: int | None
    visits: list[ServiceHistoryEntryOut]


class TimelineEventOut(BaseModel):
    event_type: str
    actor_user_id: uuid.UUID | None
    data: dict[str, Any]
    created_at: datetime


def _err(e: service.OrderError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": "order_error", "message_key": e.message_key, "params": e.params,
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


def _reject_if_terminal(order: ServiceOrder) -> None:
    """Wave 4: the documented invariant (docs/01 'Terminal orders accept no
    operational changes except payments settling an outstanding balance, and
    archiving') was enforced only by `patch_order` below — diagnosis/part-
    line/labor-line/accessory mutation had no such check. Centralized here so
    every mutating endpoint on those four resources shares one gate rather
    than repeating the `status_code in statuses.TERMINAL` condition inline.
    Payments, archive, and Owner unlock are deliberately NOT routed through
    this — they are the documented exceptions, unchanged."""
    if order.status_code in statuses.TERMINAL:
        raise HTTPException(status_code=409, detail={
            "code": "terminal", "message_key": "errors.orders.terminal_readonly",
            "params": {},
        })


def _reject_if_line_creation_not_allowed(order: ServiceOrder) -> None:
    """order-workflow-revamp WP-I (Q13d): a new part/labor line may only be
    added while the order is in Диагностика/Чака клиент/Чака части/Ремонт —
    never at intake (`received`), never on a "ready"/terminal order. Checked
    in addition to, not instead of, `_reject_if_terminal` above (a terminal
    order would already be `received`-adjacent-excluded by this check alone,
    but the terminal check's distinct 409 message stays the one a client
    sees for that case — this function only ever fires for a *non-terminal*
    status outside the allowed set, i.e. "received" or "ready")."""
    if order.status_code not in statuses.LINE_CREATION_STATUSES:
        raise HTTPException(status_code=400, detail={
            "code": "lines_not_allowed_in_status",
            "message_key": "errors.orders.lines_not_allowed_in_status", "params": {},
        })


def _resolve_catalog_item(db: TenantDbDep, tenant: TenantDep, catalog_item_id: uuid.UUID,
                          kind: str) -> CatalogItem:
    """The authoritative "this is a real, usable, right-kind catalog item"
    check every line-creation endpoint needs — 404 if it doesn't exist (or
    belongs to another tenant, same as any other scoped lookup), 400 if it
    exists but can't be used for this kind of line (ADR-BOS-013 §4: a line
    is created only from a catalog item, and only a matching, non-archived
    one)."""
    item = catalog_service.get(db, tenant, catalog_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.catalog.not_found", "params": {},
        })
    if item.kind != kind:
        raise HTTPException(status_code=400, detail={
            "code": "wrong_kind", "message_key": "errors.catalog.wrong_kind", "params": {},
        })
    if item.archived_at is not None:
        raise HTTPException(status_code=400, detail={
            "code": "archived", "message_key": "errors.catalog.archived", "params": {},
        })
    return item


def _order_for_line(db: TenantDbDep, tenant: TenantDep, order_id: uuid.UUID) -> ServiceOrder:
    """Part/labor-line and accessory PATCH endpoints only look up the line/
    item itself, not its order — this resolves the order (same tenant, FK-
    guaranteed) purely so `_reject_if_terminal` has something to check."""
    order = service.get(db, tenant, order_id)
    assert order is not None, (
        "a line/item's own order_id must always resolve within its own "
        "company — the FK guarantees this at the database level"
    )
    return order


class TechnicianLoadOut(BaseModel):
    technician_id: uuid.UUID
    active_count: int


# Registered before /orders/{order_id} so the literal path is never parsed as
# an order id.
@router.get("/orders/technician-load")
def technician_load(db: TenantDbDep, tenant: TenantDep) -> list[TechnicianLoadOut]:
    """Per-technician count of orders in Диагностика + Ремонт for the
    technician picker (WP-F, Q22). User names stay with identity's GET /users."""
    return [
        TechnicianLoadOut(technician_id=tid, active_count=n)
        for tid, n in service.technician_load(db, tenant).items()
    ]


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
    # Issue 20: an order's customer_id and its asset's current owner are
    # deliberately independent — the person bringing a vehicle in is not
    # necessarily its legal/current owner (e.g. "Използвай автомобила" keeps
    # the vehicle under its existing owner while the order itself belongs to
    # whoever is standing at the counter). Only tenant scope is enforced
    # here (assets_service.get already applies it); no customer_id equality
    # check remains.
    asset = assets_service.get(db, tenant, body.asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.assets.not_found", "params": {},
        })
    # Wave 5 Issue 12: an explicit per-order address always wins; a courier
    # order with none given falls back to the customer's own default — a
    # plain copy, taken once, here, never a live reference (a later edit to
    # Customer.delivery_address must not retroactively change this order).
    # order-workflow-revamp WP-B (Q20b): no default on file any more also
    # means "same as the main address" (the checkbox-off state), not "no
    # address" — fall back one step further to the customer's own main
    # address (individual: Customer.address; company: company_requisites.
    # address) before giving up.
    delivery_address = body.delivery_address.model_dump() if body.delivery_address else None
    if body.delivery_method == "courier" and delivery_address is None:
        if customer.delivery_address:
            delivery_address = dict(customer.delivery_address)
        else:
            main_address = (
                (customer.company_requisites or {}).get("address")
                if customer.is_company else customer.address
            )
            if main_address:
                delivery_address = {"address": main_address}

    try:
        order = service.create(
            db, tenant, customer_id=body.customer_id, asset_id=body.asset_id,
            complaint=body.complaint, priority=body.priority,
            promised_on=body.promised_on, technician_id=body.technician_id,
            mileage=body.mileage, mileage_confirmed_lower=body.mileage_confirmed_lower,
            mileage_override_comment=body.mileage_override_comment,
            delivery_method=body.delivery_method, delivery_address=delivery_address,
        )
    except service.OrderError as e:
        raise _err(e) from e
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
        adjustments=[AdjustmentOut.of(a) for a in lines.list_adjustments(db, tenant, order_id)],
        estimated_total=float(lines.order_totals(db, tenant, order_id)),
        paid_amount=float(payment_summary.paid_amount),
        balance=float(payment_summary.balance),
    )


@router.patch("/orders/{order_id}",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def patch_order(order_id: uuid.UUID, body: OrderPatch, db: TenantDbDep,
                tenant: TenantDep) -> OrderOut:
    order = _get_or_404(db, tenant, order_id)
    _reject_if_terminal(order)
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


@router.get("/assets/{asset_id}/open-order")
def asset_open_order(asset_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> OpenOrderOut:
    asset = assets_service.get(db, tenant, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.assets.not_found", "params": {},
        })
    existing = service.find_open_order_for_asset(db, tenant, asset_id)
    if existing is None:
        return OpenOrderOut()
    return OpenOrderOut(order_id=existing.id, number=existing.number,
                        status_code=existing.status_code)


@router.get("/assets/{asset_id}/service-history")
def asset_service_history(asset_id: uuid.UUID, db: TenantDbDep,
                          tenant: TenantDep) -> AssetServiceHistoryOut:
    """Wave 3 Issues 21/26/27: every visit against this vehicle, keyed on
    asset_id — survives an ownership change (Issue 20) since it is never
    filtered by customer_id. Lives here rather than in `serviceflow.assets`
    because the data is fundamentally order data; `assets_service` is
    already a legal import from service_orders (see create_order above),
    so no new cross-module edge is introduced."""
    asset = assets_service.get(db, tenant, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.assets.not_found", "params": {},
        })
    orders = service.list_orders_for_asset(db, tenant, asset_id)
    customers = customers_service.get_many(db, tenant, (o.customer_id for o in orders))
    visits = [
        ServiceHistoryEntryOut(
            order_id=o.id, order_number=o.number, created_at=o.created_at,
            status_code=o.status_code, customer_id=o.customer_id,
            customer_name=customers[o.customer_id].name if o.customer_id in customers else "",
            complaint=o.complaint, mileage=o.mileage,
        )
        for o in orders
    ]
    latest_order_mileage = next((v.mileage for v in visits if v.mileage is not None), None)
    legacy_mileage = asset.field_values.get("mileage")
    current_mileage = latest_order_mileage
    if current_mileage is None and isinstance(legacy_mileage, int | float):
        current_mileage = int(legacy_mileage)
    return AssetServiceHistoryOut(
        asset_id=asset.id, asset_label=asset.label,
        current_mileage=current_mileage, visits=visits,
    )


# --- Diagnosis (0..1 per order, edited in place — docs/01 §Diagnosis) ---------

@router.put("/orders/{order_id}/diagnosis",
           dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def put_diagnosis(order_id: uuid.UUID, body: DiagnosisIn, db: TenantDbDep,
                  tenant: TenantDep) -> DiagnosisOut:
    order = _get_or_404(db, tenant, order_id)
    _reject_if_terminal(order)
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
    _reject_if_terminal(order)
    _reject_if_line_creation_not_allowed(order)
    if body.state not in lines.ADD_PART_STATES:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_state", "message_key": "errors.part_lines.invalid_state",
            "params": {},
        })
    item = _resolve_catalog_item(db, tenant, body.catalog_item_id, "part")
    line = lines.add_part_line(db, tenant, order, catalog_item=item, qty=body.qty,
                               state=body.state, has_warranty=body.has_warranty)
    suggested = lines.suggest_status_after_part_add(order.status_code, line.state)
    return PartLineOut.of(line, suggested_status=suggested)


@router.patch("/part-lines/{line_id}",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def patch_part_line(line_id: uuid.UUID, body: PartLinePatch, db: TenantDbDep,
                    tenant: TenantDep) -> PartLineOut:
    line = lines.get_part_line(db, tenant, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.part_lines.not_found", "params": {},
        })
    order = _order_for_line(db, tenant, line.order_id)
    _reject_if_terminal(order)
    if body.state is not None and body.state not in PART_STATES:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_state", "message_key": "errors.part_lines.invalid_state",
            "params": {},
        })
    fields = body.model_dump(exclude_unset=True)
    line = lines.update_part_line(db, tenant, line, fields)
    suggested = (
        lines.suggest_status_after_part_state_change(db, tenant, order, line.state)
        if "state" in fields else None
    )
    return PartLineOut.of(line, suggested_status=suggested)


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
    _reject_if_terminal(order)
    _reject_if_line_creation_not_allowed(order)
    item = _resolve_catalog_item(db, tenant, body.catalog_item_id, "labor")
    line = lines.add_labor_line(db, tenant, order, catalog_item=item, qty=body.qty,
                                duration_min=body.duration_min, performed_by=body.performed_by)
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
    _reject_if_terminal(_order_for_line(db, tenant, line.order_id))
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
    _reject_if_terminal(order)
    # order-workflow-revamp WP-H (Q16/Q16b): the UI hides the add-accessory
    # form for an asset type with accessories=False (automotive) — this is
    # the authoritative guard, same division of labor as mileage's
    # service-side re-check. Historic accessories on such an order (added
    # before this flag existed) are untouched; only adding a NEW one is
    # blocked.
    asset = assets_service.get(db, tenant, order.asset_id)
    asset_type = assets_service.get_type_by_id(db, tenant, asset.asset_type_id) \
        if asset is not None else None
    if asset_type is not None and not asset_type.accessories:
        raise HTTPException(status_code=400, detail={
            "code": "accessories_not_supported", "message_key": "errors.accessories.not_supported",
            "params": {},
        })
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
    _reject_if_terminal(_order_for_line(db, tenant, item.order_id))
    item = lines.mark_accessory_returned(db, tenant, item, body.returned)
    return AccessoryOut.of(item)


# --- Order adjustments (WP-I, Q13, resolves docs/01 OQ-5) -------------------

@router.get("/orders/{order_id}/adjustments")
def list_adjustments(order_id: uuid.UUID, db: TenantDbDep,
                     tenant: TenantDep) -> list[AdjustmentOut]:
    _get_or_404(db, tenant, order_id)
    return [AdjustmentOut.of(a) for a in lines.list_adjustments(db, tenant, order_id)]


@router.post("/orders/{order_id}/adjustments",
            dependencies=[Depends(require_csrf), Depends(require_owner),
                         Depends(require_subscription_ok)],
            status_code=201)
def add_adjustment(order_id: uuid.UUID, body: AdjustmentIn, db: TenantDbDep,
                   tenant: TenantDep) -> AdjustmentOut:
    order = _get_or_404(db, tenant, order_id)
    _reject_if_terminal(order)
    adjustment = lines.add_adjustment(db, tenant, order, amount=body.amount, reason=body.reason)
    return AdjustmentOut.of(adjustment)


# --- Protocol (приемо-предавателен протокол) --------------------------------
# Intake variant (docs/13 Етап-2 scope note) reads live order/customer/asset
# data — safe, since intake happens once and is never reprinted against
# changed history. Delivery variant (Wave 4 Issue 7) reads ONLY the frozen
# `completion_snapshot` built at delivery time — never live data — so a
# reprint months later still shows exactly what was true at delivery.

@router.get("/orders/{order_id}/protocol.pdf")
def order_protocol(order_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep,
                   type: str = "intake") -> Response:  # param name matches docs/09 ?type=
    if type not in ("intake", "delivery"):
        raise HTTPException(status_code=400, detail={
            "code": "invalid_type", "message_key": "errors.protocol.invalid_type", "params": {},
        })

    order = _get_or_404(db, tenant, order_id)

    if type == "delivery":
        if order.completion_snapshot is None:
            # Covers both "never delivered yet" and "delivered before this
            # column existed" identically — no live-data reconstruction
            # either way (Wave 4 audit's explicit decision).
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message_key": "errors.protocol.delivery_unavailable",
                "params": {},
            })
        pdf_bytes = protocol.generate_delivery_protocol(
            protocol.build_delivery_protocol_data(order.completion_snapshot)
        )
        return Response(
            content=pdf_bytes, media_type="application/pdf",
            headers={
                "Content-Disposition":
                    f'inline; filename="protokol-predavane-{order.number}.pdf"',
            },
        )

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


class ProtocolEmailRequest(BaseModel):
    include_warranty: bool = False


@router.post("/orders/{order_id}/protocol/email",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def email_completion_protocol(order_id: uuid.UUID, body: ProtocolEmailRequest,
                              db: TenantDbDep, tenant: TenantDep) -> dict[str, bool]:
    order = _get_or_404(db, tenant, order_id)
    try:
        service.send_completion_protocol_email(
            db, tenant, order, include_warranty=body.include_warranty,
        )
    except service.OrderError as e:
        raise _err(e) from e
    return {"sent": True}
