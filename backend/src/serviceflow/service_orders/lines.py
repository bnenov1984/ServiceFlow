"""Part lines, labor lines, accessories, order adjustments — all IN the
ServiceOrder aggregate (docs/01 §4). Money totals feed the order display;
VAT/invoicing is Етап 4.

order-workflow-revamp WP-I (Q12/Q13, ADR-BOS-013): part/labor lines are
created only from a `catalog.CatalogItem` — `add_part_line`/`add_labor_line`
take a resolved `CatalogItem` (never a free-typed name/price) and snapshot
its fields onto the new row. Status-gating (Q13d: only while the order is in
Диагностика/Чака клиент/Чака части/Ремонт) and catalog-item resolution
(exists, right company, right `kind`, not archived) are the router's job —
same division of labor `_reject_if_terminal` already has for the terminal
check: this module enforces the data shape, the router enforces the request
preconditions.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.identity import contracts as identity_contracts
from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.events import DomainEvent, publish
from serviceflow.catalog.models import CatalogItem
from serviceflow.service_orders.models import (
    AccessoryItem,
    LaborLine,
    OrderAdjustment,
    PartLine,
    ServiceOrder,
)

# Wave 2 Issue 33: simplified V1 model — "ordered" (assigned/requested for
# this order, regardless of physical stock) and "installed". Migration 0022
# backfills existing rows (needed/received/removed -> ordered); no inventory/
# stock tracking is introduced by this simplification. order-workflow-revamp
# WP-J will revisit this 3-way split (#27); untouched by WP-I.
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


def add_part_line(db: Session, ctx: TenantContext, order: ServiceOrder, *,
                  catalog_item: CatalogItem, qty: int,
                  warranty_days: int | None = None) -> PartLine:
    """Snapshots `catalog_item`'s name/code/price onto the new line (BR-3: a
    later catalog price change never retroactively changes it). The caller
    has already confirmed `catalog_item.kind == "part"` and it isn't
    archived — this function trusts that, the same way `add_accessory`
    below trusts its caller for the order's terminal state."""
    # Cleanup batch Issue 7: explicit (including 0, "Без гаранция") always
    # wins; omitted falls back to the company's configured parts default,
    # if one exists, applied once at creation only — never retroactively
    # for existing PartLines, and never re-derived later.
    if warranty_days is None:
        warranty_days = identity_contracts.get_warranty_defaults(
            db, ctx.company_id,
        )["parts_days"]
    line = PartLine(
        company_id=ctx.company_id, order_id=order.id, catalog_item_id=catalog_item.id,
        name=catalog_item.name, code=catalog_item.code, qty=qty,
        unit_cost=catalog_item.unit_cost or Decimal("0"), unit_price=catalog_item.sale_price,
        warranty_days=warranty_days,
    )
    db.add(line)
    db.flush()
    _event(db, ctx, order.id, "part_added", {"name": line.name, "qty": qty})
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
                   catalog_item: CatalogItem, qty: Decimal,
                   duration_min: int | None = None,
                   performed_by: uuid.UUID | None = None) -> LaborLine:
    """Same catalog/snapshot discipline as `add_part_line` above. `qty` is a
    plain count for a `unit="pcs"` item, hours for a `unit="hour"` one — the
    caller never has to branch, both are the same `Decimal`. `duration_min`
    is independent of the catalog — an optional "how long did it actually
    take" note (docs/01 §LaborLine), never a price/name field."""
    line = LaborLine(
        company_id=ctx.company_id, order_id=order.id, catalog_item_id=catalog_item.id,
        description=catalog_item.name, code=catalog_item.code, unit=catalog_item.unit,
        qty=qty, unit_price=catalog_item.sale_price, unit_cost=catalog_item.unit_cost,
        duration_min=duration_min, performed_by=performed_by,
    )
    db.add(line)
    db.flush()
    _event(db, ctx, order.id, "labor_added", {"description": line.description})
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


# --- Order adjustments (WP-I, Q13, resolves docs/01 OQ-5) -------------------

def list_adjustments(db: Session, ctx: TenantContext,
                     order_id: uuid.UUID) -> list[OrderAdjustment]:
    return list(db.scalars(
        scoped(select(OrderAdjustment), OrderAdjustment, ctx)
        .where(OrderAdjustment.order_id == order_id)
        .order_by(OrderAdjustment.created_at)
    ))


def add_adjustment(db: Session, ctx: TenantContext, order: ServiceOrder, *,
                   amount: Decimal, reason: str) -> OrderAdjustment:
    """Append-only (docs/01 OQ-5) — a wrong adjustment is corrected by adding
    an offsetting one, never by editing/deleting this row. Owner-only is
    enforced at the router layer (`require_owner`), same as every other
    Owner-gated mutation."""
    adjustment = OrderAdjustment(
        company_id=ctx.company_id, order_id=order.id, amount=amount, reason=reason,
        created_by=ctx.user_id,
    )
    db.add(adjustment)
    db.flush()
    _event(db, ctx, order.id, "adjustment_added", {"amount": str(amount), "reason": reason})
    db.commit()
    return adjustment


# --- Totals (BR-3: always derived, never stored — Етап 4 adds VAT/invoicing) ---

def order_totals(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> Decimal:
    parts = sum((p.qty * p.unit_price for p in list_part_lines(db, ctx, order_id)),
               Decimal("0"))
    labor = sum((line.qty * line.unit_price for line in list_labor_lines(db, ctx, order_id)),
               Decimal("0"))
    adjustments = sum((a.amount for a in list_adjustments(db, ctx, order_id)), Decimal("0"))
    return parts + labor + adjustments
