"""Commercial Documents & Invoicing (docs/01 §Payment, docs/08 §commercial).

Payment lands ahead of Invoice (docs/13 Етап 4): it needs no numbering, no
immutability, no VAT rules, and docs/08's own schema already declares
invoice_id as nullable — a payment never requires an invoice to exist.
`invoice_id` therefore carries no FK constraint yet; the future Invoice
migration adds `fk_payments_invoice_id_invoices` once that table exists.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base
from business_os.shared_kernel.ids import new_id

PAYMENT_METHODS = ("cash", "card", "bank")


class Payment(Base):
    """Unified payment/refund record (docs/01 §Payment): one mechanism for
    deposits, partial payments and refunds. Corrections are new offsetting
    records — a Payment is never mutated or deleted once recorded."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_orders.id"), index=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), default=None)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    method: Mapped[str]
    is_refund: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str] = mapped_column(default="", server_default="")
    received_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    received_at: Mapped[datetime]
