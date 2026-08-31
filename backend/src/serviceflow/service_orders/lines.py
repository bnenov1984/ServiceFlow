"""Part lines, labor lines, accessories — all IN the ServiceOrder aggregate
(docs/01 §4). Money totals feed the order display; VAT/invoicing is Етап 4."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.events import DomainEvent, publish
from serviceflow.service_orders.models import AccessoryItem, LaborLine, PartLine, ServiceOrder

# Wave 2 Issue 33: simplified V1 model — "ordered" (assigned/requested for
# this order, regardless of physical stock) and "installed". Migration 0022
# backfills existing rows (needed/received/removed -> ordered); no inventory/
# stock tracking is introduced by this simplification.
PART_STATES = ("ordered", "installed")


def _event(db: Session, ctx: TenantContext, order_id: uuid.UUID, type_: str,
           data: dict[str, Any]) -> None:
    publish(db, DomainEvent(type=type_, company_id=ctx.company_id,
                            actor_user_id=ctx.user_id, subject_id=order_id, data=data))


# --- Part lines ---------------------------------------------------------

def list_part_lines(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> list[PartLine]:
    return list(db.scalars(
        scoped(select(PartLine), PartLine, ctx).where(PartLine.order_id == order_id)
    ))


def add_part_line(db: Session, ctx: TenantContext, order: ServiceOrder, *, name: str,
                  qty: int, unit_cost: Decimal, unit_price: Decimal) -> PartLine:
    line = PartLine(company_id=ctx.company_id, order_id=order.id, name=name, qty=qty,
                    unit_cost=unit_cost, unit_price=unit_price)
    db.add(line)
    db.flush()
    _event(db, ctx, order.id, "part_added", {"name": name, "qty": qty})
    db.commit()
    return line


def get_part_line(db: Session, ctx: TenantContext, line_id: uuid.UUID) -> PartLine | None:
    return db.scalar(scoped(select(PartLine), PartLine, ctx).where(PartLine.id == line_id))


def update_part_line(db: Session, ctx: TenantContext, line: PartLine,
                     fields: dict[str, Any]) -> PartLine:
    prev_state = line.state
    for key, value in fields.items():
        setattr(line, key, value)
    if "state" in fields and fields["state"] != prev_state:
        event_type = {"ordered": "part_ordered"}.get(fields["state"], "part_state_changed")
        _event(db, ctx, line.order_id, event_type,
              {"name": line.name, "from": prev_state, "to": fields["state"]})
    db.commit()
    return line


# --- Labor lines ---------------------------------------------------------

def list_labor_lines(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> list[LaborLine]:
    return list(db.scalars(
        scoped(select(LaborLine), LaborLine, ctx).where(LaborLine.order_id == order_id)
    ))


def add_labor_line(db: Session, ctx: TenantContext, order: ServiceOrder, *,
                   description: str, qty: int, unit_price: Decimal,
                   duration_min: int | None = None,
                   performed_by: uuid.UUID | None = None) -> LaborLine:
    line = LaborLine(company_id=ctx.company_id, order_id=order.id, description=description,
                     qty=qty, unit_price=unit_price, duration_min=duration_min,
                     performed_by=performed_by)
    db.add(line)
    db.flush()
    _event(db, ctx, order.id, "labor_added", {"description": description})
    db.commit()
    return line


def get_labor_line(db: Session, ctx: TenantContext, line_id: uuid.UUID) -> LaborLine | None:
    return db.scalar(scoped(select(LaborLine), LaborLine, ctx).where(LaborLine.id == line_id))


def update_labor_line(db: Session, ctx: TenantContext, line: LaborLine,
                      fields: dict[str, Any]) -> LaborLine:
    for key, value in fields.items():
        setattr(line, key, value)
    db.commit()
    return line


# --- Accessories ----------------------------------------------------------

def list_accessories(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> list[AccessoryItem]:
    return list(db.scalars(
        scoped(select(AccessoryItem), AccessoryItem, ctx).where(
            AccessoryItem.order_id == order_id)
    ))


def add_accessory(db: Session, ctx: TenantContext, order: ServiceOrder, *, name: str,
                  qty: int) -> AccessoryItem:
    item = AccessoryItem(company_id=ctx.company_id, order_id=order.id, name=name, qty=qty)
    db.add(item)
    db.commit()
    return item


def get_accessory(db: Session, ctx: TenantContext, item_id: uuid.UUID) -> AccessoryItem | None:
    return db.scalar(
        scoped(select(AccessoryItem), AccessoryItem, ctx).where(AccessoryItem.id == item_id)
    )


def mark_accessory_returned(db: Session, ctx: TenantContext, item: AccessoryItem,
                           returned: bool) -> AccessoryItem:
    item.returned = returned
    db.commit()
    return item


# --- Totals (BR-3: always derived, never stored — Етап 4 adds VAT/invoicing) ---

def order_totals(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> Decimal:
    parts = sum((p.qty * p.unit_price for p in list_part_lines(db, ctx, order_id)),
               Decimal("0"))
    labor = sum((line.qty * line.unit_price for line in list_labor_lines(db, ctx, order_id)),
               Decimal("0"))
    return parts + labor
