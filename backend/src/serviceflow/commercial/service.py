"""Payment recording (docs/01 §Payment). Money totals stay derived, never
stored (BR-3): paid_amount and balance are computed here, not persisted."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.events import DomainEvent, publish
from serviceflow.commercial.models import Payment
from serviceflow.service_orders import lines
from serviceflow.service_orders.models import ServiceOrder


def _now() -> datetime:
    return datetime.now(UTC)


def add_payment(db: Session, ctx: TenantContext, order: ServiceOrder, *, amount: Decimal,
                method: str, is_refund: bool = False, note: str = "") -> Payment:
    payment = Payment(
        company_id=ctx.company_id, order_id=order.id, amount=amount, method=method,
        is_refund=is_refund, note=note, received_by=ctx.user_id, received_at=_now(),
    )
    db.add(payment)
    db.flush()
    publish(db, DomainEvent(
        type="payment_refunded" if is_refund else "payment_recorded",
        company_id=ctx.company_id, actor_user_id=ctx.user_id, order_id=order.id,
        data={"amount": str(amount), "method": method},
    ))
    db.commit()
    return payment


def list_for_order(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> list[Payment]:
    return list(db.scalars(
        scoped(select(Payment), Payment, ctx)
        .where(Payment.order_id == order_id)
        .order_by(Payment.received_at)
    ))


def paid_amount(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> Decimal:
    """Net amount paid: recorded payments minus refunds (BR-3, docs/01 §Payment).
    Never stored — always derived from the payment records."""
    total = Decimal("0")
    for p in list_for_order(db, ctx, order_id):
        total += -p.amount if p.is_refund else p.amount
    return total


def balance(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> Decimal:
    """Outstanding balance: canonical order total (lines.order_totals, the
    single BR-3 total formula) minus net paid. May go negative (overpayment/
    credit) — docs/01 does not prohibit it, so it is not rejected here."""
    return lines.order_totals(db, ctx, order_id) - paid_amount(db, ctx, order_id)
