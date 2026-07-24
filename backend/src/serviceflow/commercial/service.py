"""Payment recording (docs/01 §Payment) and Invoice drafts (docs/01 §Invoice).

Money totals stay derived, never stored (BR-3): paid_amount and balance are
computed here, not persisted. Invoice draft creation/editing is this file's
other half — issue, numbering, annul/reissue, PDF and VAT computation are a
later slice (see commercial/models.py docstring); everything below only ever
produces/edits `status="draft"` rows."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.events import DomainEvent, publish
from serviceflow.commercial.models import Invoice, InvoiceLine, Payment
from serviceflow.service_orders import contracts as orders_contracts


class InvoiceError(Exception):
    def __init__(self, message_key: str, status: int = 409) -> None:
        self.message_key = message_key
        self.status = status


def _now() -> datetime:
    return datetime.now(UTC)


def add_payment(db: Session, ctx: TenantContext, order_id: uuid.UUID, *, amount: Decimal,
                method: str, is_refund: bool = False, note: str = "") -> Payment:
    payment = Payment(
        company_id=ctx.company_id, subject_id=order_id, amount=amount, method=method,
        is_refund=is_refund, note=note, received_by=ctx.user_id, received_at=_now(),
    )
    db.add(payment)
    db.flush()
    publish(db, DomainEvent(
        type="payment_refunded" if is_refund else "payment_recorded",
        company_id=ctx.company_id, actor_user_id=ctx.user_id, subject_id=order_id,
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
    """Outstanding balance: canonical order total (via service_orders'
    public contract — the single BR-3 total formula, never reimplemented
    here) minus net paid. May go negative (overpayment/credit) — docs/01
    does not prohibit it, so it is not rejected here."""
    return orders_contracts.get_order_total(db, ctx, order_id) - paid_amount(db, ctx, order_id)


# --- Invoice drafts (docs/01 §Invoice) --------------------------------------
# Draft only: create, list, read, replace lines. No issue/annul/reissue/PDF/
# VAT computation — see commercial/models.py's module docstring for why.

def create_draft(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> Invoice:
    """Prefilled from the order's part + labor lines via service_orders'
    public contract (docs/09: "draft prefilled from lines") — never
    service_orders.models/.lines directly. A one-time copy: later edits to
    the order's own lines do not retroactively change this draft, matching
    how the draft becomes an independently-editable document once created."""
    invoice = Invoice(company_id=ctx.company_id, subject_id=order_id, status="draft")
    db.add(invoice)
    db.flush()
    for sort, line in enumerate(orders_contracts.get_order_lines(db, ctx, order_id)):
        db.add(InvoiceLine(
            company_id=ctx.company_id, invoice_id=invoice.id, description=line.description,
            qty=line.qty, unit_price=line.unit_price, source=line.source, sort=sort,
        ))
    db.commit()
    return invoice


def get(db: Session, ctx: TenantContext, invoice_id: uuid.UUID) -> Invoice | None:
    return db.scalar(scoped(select(Invoice), Invoice, ctx).where(Invoice.id == invoice_id))


def list_invoices(db: Session, ctx: TenantContext, *, status: str | None = None,
                  order_id: uuid.UUID | None = None) -> list[Invoice]:
    stmt = scoped(select(Invoice), Invoice, ctx)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if order_id:
        stmt = stmt.where(Invoice.order_id == order_id)
    return list(db.scalars(stmt.order_by(Invoice.created_at.desc())))


def list_lines(db: Session, ctx: TenantContext, invoice_id: uuid.UUID) -> list[InvoiceLine]:
    return list(db.scalars(
        scoped(select(InvoiceLine), InvoiceLine, ctx)
        .where(InvoiceLine.invoice_id == invoice_id)
        .order_by(InvoiceLine.sort)
    ))


def draft_total(db: Session, ctx: TenantContext, invoice_id: uuid.UUID) -> Decimal:
    """Informational only — never stored. The frozen net/vat/gross columns
    (docs/08) stay NULL until issue computes and freezes them; this is a
    live sum of the current lines, purely for the draft view."""
    return sum(
        (line.qty * line.unit_price for line in list_lines(db, ctx, invoice_id)),
        Decimal("0"),
    )


def replace_lines(db: Session, ctx: TenantContext, invoice: Invoice,
                  lines: list[dict[str, Any]]) -> Invoice:
    """Whole-document replace (docs/09 lists no separate invoice_lines
    endpoints, unlike part-lines/labor-lines) — draft only."""
    if invoice.status != "draft":
        raise InvoiceError("errors.invoices.not_draft")
    db.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id))
    for sort, fields in enumerate(lines):
        db.add(InvoiceLine(
            company_id=ctx.company_id, invoice_id=invoice.id,
            description=fields["description"], qty=fields["qty"],
            unit_price=fields["unit_price"], vat_rate=fields.get("vat_rate"),
            source=fields["source"], sort=sort,
        ))
    invoice.row_version += 1
    db.commit()
    return invoice
