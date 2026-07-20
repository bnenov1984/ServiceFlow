"""Service Orders' public application contract (docs/business-os/04 rule R4 —
the first real commercial ↔ service_orders edge). Mirrors
business_os/identity/contracts.py's shape, applied to a lateral module edge
instead of the Core edge.

Two directions live in this one file, matching a module's "public contract
surface" covering both what it exposes to be read and what it declares it
needs injected from elsewhere:

- **Outbound** (functions another module calls): `get_order_summary`,
  `get_order_total`, `get_order_lines` (the last one added for Invoice draft
  prefill — docs/09 "draft prefilled from lines"). Commercial reads order
  data through these only — never `service_orders.models`/`.service`/
  `.lines` directly.
- **Inbound port** (`PaymentSummaryProvider`): service_orders needs
  paid_amount/balance to enrich GET /orders/{id}, but that data is owned by
  `commercial`. Rather than importing commercial (which would recreate the
  exact cycle this file exists to remove), service_orders declares the shape
  it needs and commercial registers an implementation — wired once at
  startup by the composition root (serviceflow/main.py), the same
  register-at-import-time shape `shared_kernel.events.subscribe` already
  uses for the timeline subscriber.

Internal service_orders modules (`.models`, `.service`, `.lines`, `.protocol`,
`.statuses`, `.router`) are implementation detail; importing them from outside
service_orders' own package (or the composition root) is what the
`service-orders-public-boundary` import-linter contract (backend/.importlinter)
mechanically blocks.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext
from serviceflow.service_orders import lines as _lines
from serviceflow.service_orders import service as _service


@dataclass(frozen=True)
class OrderSummary:
    """The subset of order data another module may need — never the ORM
    model itself. `archived` gates whether an order still accepts operational
    changes; docs/01 §ServiceOrder invariants."""

    id: uuid.UUID
    number: str
    customer_id: uuid.UUID
    asset_id: uuid.UUID
    archived: bool


def get_order_summary(db: Session, ctx: TenantContext,
                      order_id: uuid.UUID) -> OrderSummary | None:
    """The sanctioned way for another module to look up an order. Returns
    None if the order doesn't exist or isn't in the caller's tenant (the
    scoped() chokepoint already enforces that inside `_service.get`)."""
    order = _service.get(db, ctx, order_id)
    if order is None:
        return None
    return OrderSummary(
        id=order.id, number=order.number, customer_id=order.customer_id,
        asset_id=order.asset_id, archived=order.archived_at is not None,
    )


def get_order_total(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> Decimal:
    """The canonical order total (BR-3) — the single money formula every
    consumer must reuse, never reimplement. Wraps `lines.order_totals`."""
    return _lines.order_totals(db, ctx, order_id)


@dataclass(frozen=True)
class OrderLineSummary:
    """One billable line, sourced from either a PartLine or a LaborLine —
    the shape commercial needs to prefill an invoice draft (docs/09: "draft
    prefilled from lines"), never the ORM rows themselves."""

    description: str
    qty: int
    unit_price: Decimal
    source: str  # "part" | "labor" — matches invoice_lines.source (docs/08)


def get_order_lines(db: Session, ctx: TenantContext,
                    order_id: uuid.UUID) -> list[OrderLineSummary]:
    """Part + labor lines, in the order they'd prefill an invoice draft.
    Read-only snapshot at call time — the caller decides whether/when to
    copy these into its own records; this function does not persist
    anything."""
    parts = [
        OrderLineSummary(description=p.name, qty=p.qty, unit_price=p.unit_price,
                         source="part")
        for p in _lines.list_part_lines(db, ctx, order_id)
    ]
    labor = [
        OrderLineSummary(description=line.description, qty=line.qty,
                         unit_price=line.unit_price, source="labor")
        for line in _lines.list_labor_lines(db, ctx, order_id)
    ]
    return parts + labor


@dataclass(frozen=True)
class PaymentSummary:
    """paid_amount/balance for one order — owned in shape by service_orders
    (it's what GET /orders/{id} exposes), computed by whoever implements
    PaymentSummaryProvider (commercial)."""

    paid_amount: Decimal
    balance: Decimal


class PaymentSummaryProvider(Protocol):
    def __call__(self, db: Session, ctx: TenantContext,
                order_id: uuid.UUID) -> PaymentSummary: ...


_payment_summary_provider: PaymentSummaryProvider | None = None


def register_payment_summary_provider(provider: PaymentSummaryProvider) -> None:
    """Called once by the composition root (serviceflow/main.py) at import
    time, wiring commercial's implementation into this port. service_orders
    never imports commercial to make this call happen — commercial imports
    *this* module (the allowed direction) to know the shape it must satisfy,
    and the composition root, which is allowed to import everything, performs
    the actual wiring."""
    global _payment_summary_provider
    _payment_summary_provider = provider


def get_payment_summary(db: Session, ctx: TenantContext,
                        order_id: uuid.UUID) -> PaymentSummary:
    assert _payment_summary_provider is not None, (
        "no PaymentSummaryProvider registered — serviceflow.main must import "
        "and wire commercial.contracts.get_payment_summary before the app "
        "serves requests"
    )
    return _payment_summary_provider(db, ctx, order_id)
