"""Commercial endpoints per docs/09 §Commercial documents.

Payment is deliberately outside the ServiceOrder aggregate (docs/01 §4, same
category as Task/Attachment/ContactRecord) — service_orders/router.py's
OrderDetailOut carries only the derived paid_amount/balance summary, not a raw
payments list, matching how Task/Attachment/ContactRecord are exposed via
their own endpoints rather than embedded.

Invoice is a Draft-only slice here: POST creates a draft prefilled from the
order's lines (via service_orders' public contract — never its internal
models), GET lists/reads, PATCH replaces the line set (drafts only, docs/09
lists no separate invoice_lines sub-resource, unlike part-lines/labor-lines).
No issue/annul/reissue/PDF endpoints and no `?q=` search yet — nothing is
issue-numbered or buyer-snapshotted yet for `q` to usefully search across
(see commercial/models.py's module docstring)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from business_os.identity.deps import TenantDbDep, TenantDep, require_csrf
from serviceflow.commercial import service
from serviceflow.commercial.models import Invoice, InvoiceLine, Payment
from serviceflow.service_orders import contracts as orders_contracts

router = APIRouter()


class PaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str = Field(pattern="^(cash|card|bank)$")
    is_refund: bool = False
    note: str = Field(default="", max_length=1000)


class PaymentOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    invoice_id: uuid.UUID | None
    amount: float
    method: str
    is_refund: bool
    note: str
    received_by: uuid.UUID
    received_at: datetime

    @staticmethod
    def of(p: Payment) -> "PaymentOut":
        return PaymentOut(
            id=p.id, order_id=p.order_id, invoice_id=p.invoice_id, amount=float(p.amount),
            method=p.method, is_refund=p.is_refund, note=p.note, received_by=p.received_by,
            received_at=p.received_at,
        )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "code": "not_found", "message_key": "errors.orders.not_found", "params": {},
    })


@router.post("/orders/{order_id}/payments", dependencies=[Depends(require_csrf)],
             status_code=201)
def add_payment(order_id: uuid.UUID, body: PaymentIn, db: TenantDbDep,
                tenant: TenantDep) -> PaymentOut:
    order = orders_contracts.get_order_summary(db, tenant, order_id)
    if order is None:
        raise _not_found()
    # Terminal orders still accept payments settling an outstanding balance
    # (docs/01 §ServiceOrder invariants) — only archiving closes the door.
    if order.archived:
        raise HTTPException(status_code=409, detail={
            "code": "order_error", "message_key": "errors.orders.archived", "params": {},
        })
    payment = service.add_payment(
        db, tenant, order.id, amount=body.amount, method=body.method,
        is_refund=body.is_refund, note=body.note,
    )
    return PaymentOut.of(payment)


# --- Invoice drafts (docs/01 §Invoice) --------------------------------------

class InvoiceLineIn(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    qty: int = Field(default=1, ge=1)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    vat_rate: Decimal | None = Field(default=None, ge=0)
    source: str = Field(pattern="^(labor|part|manual|adjustment)$")


class InvoiceLineOut(BaseModel):
    id: uuid.UUID
    description: str
    qty: int
    unit_price: float
    vat_rate: float | None
    source: str

    @staticmethod
    def of(line: InvoiceLine) -> "InvoiceLineOut":
        return InvoiceLineOut(
            id=line.id, description=line.description, qty=line.qty,
            unit_price=float(line.unit_price),
            vat_rate=float(line.vat_rate) if line.vat_rate is not None else None,
            source=line.source,
        )


class InvoicePatchIn(BaseModel):
    lines: list[InvoiceLineIn]


class InvoiceOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    status: str
    number: int | None
    currency: str
    row_version: int

    @staticmethod
    def of(invoice: Invoice) -> "InvoiceOut":
        return InvoiceOut(
            id=invoice.id, order_id=invoice.order_id, status=invoice.status,
            number=invoice.number, currency=invoice.currency,
            row_version=invoice.row_version,
        )


class InvoiceDetailOut(InvoiceOut):
    lines: list[InvoiceLineOut]
    draft_total: float  # informational sum of current lines — never stored (BR-3)


def _invoice_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "code": "not_found", "message_key": "errors.invoices.not_found", "params": {},
    })


def _invoice_error(e: service.InvoiceError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": "invoice_error", "message_key": e.message_key, "params": {},
    })


def _invoice_detail(db: TenantDbDep, tenant: TenantDep, invoice: Invoice) -> InvoiceDetailOut:
    return InvoiceDetailOut(
        **InvoiceOut.of(invoice).model_dump(),
        lines=[InvoiceLineOut.of(line) for line in service.list_lines(db, tenant, invoice.id)],
        draft_total=float(service.draft_total(db, tenant, invoice.id)),
    )


@router.post("/orders/{order_id}/invoices", dependencies=[Depends(require_csrf)],
             status_code=201)
def create_invoice_draft(order_id: uuid.UUID, db: TenantDbDep,
                         tenant: TenantDep) -> InvoiceDetailOut:
    order = orders_contracts.get_order_summary(db, tenant, order_id)
    if order is None:
        raise _not_found()
    if order.archived:
        raise HTTPException(status_code=409, detail={
            "code": "order_error", "message_key": "errors.orders.archived", "params": {},
        })
    invoice = service.create_draft(db, tenant, order.id)
    return _invoice_detail(db, tenant, invoice)


@router.get("/invoices")
def list_invoices(db: TenantDbDep, tenant: TenantDep,
                  status: str | None = None) -> list[InvoiceOut]:
    return [InvoiceOut.of(i) for i in service.list_invoices(db, tenant, status=status)]


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> InvoiceDetailOut:
    invoice = service.get(db, tenant, invoice_id)
    if invoice is None:
        raise _invoice_not_found()
    return _invoice_detail(db, tenant, invoice)


@router.patch("/invoices/{invoice_id}", dependencies=[Depends(require_csrf)])
def patch_invoice(invoice_id: uuid.UUID, body: InvoicePatchIn, db: TenantDbDep,
                  tenant: TenantDep) -> InvoiceDetailOut:
    invoice = service.get(db, tenant, invoice_id)
    if invoice is None:
        raise _invoice_not_found()
    fields: list[dict[str, Any]] = [line.model_dump() for line in body.lines]
    try:
        invoice = service.replace_lines(db, tenant, invoice, fields)
    except service.InvoiceError as e:
        raise _invoice_error(e) from e
    return _invoice_detail(db, tenant, invoice)
