"""Payment endpoints per docs/09 §Commercial documents: POST /orders/{id}/payments.

Payment is deliberately outside the ServiceOrder aggregate (docs/01 §4, same
category as Task/Attachment/ContactRecord) — service_orders/router.py's
OrderDetailOut carries only the derived paid_amount/balance summary, not a raw
payments list, matching how Task/Attachment/ContactRecord are exposed via
their own endpoints rather than embedded. Invoice is Етап 4, not this slice."""

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from business_os.identity.deps import TenantDbDep, TenantDep, require_csrf
from serviceflow.commercial import service
from serviceflow.commercial.models import Payment
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
