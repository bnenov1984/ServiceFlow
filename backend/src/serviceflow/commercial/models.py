"""Commercial Documents & Invoicing (docs/01 §Invoice/§Payment, docs/08
§commercial).

Payment landed ahead of Invoice (docs/13 Етап 4): it needed no numbering, no
immutability, no VAT rules. `payments.invoice_id` was nullable with no FK
until `invoices` existed (migration 0008's docstring promised the future
Invoice migration would add it) — migration 0009 fulfills that.

Invoice itself lands here as a **Draft-only slice**: creation prefilled from
an order's part/labor lines (via service_orders' public contract, never its
internal models), listing, detail, and draft line edits. `status` is always
`"draft"` for every row this slice creates — `number`, `issued_at`,
`seller`, `buyer`, `net`/`vat`/`gross`, `annuls_invoice_id`, `annul_reason`,
`pdf_storage_key` all stay unset. Issue (gapless numbering, requisite
snapshot, immutability), annul/reissue, PDF rendering, and VAT computation
are explicitly a later slice — the schema already carries their columns
(docs/08 is frozen) so no future ALTER TABLE is needed, but no code here
populates or enforces them yet.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id

PAYMENT_METHODS = ("cash", "card", "bank")
INVOICE_STATUSES = ("draft", "issued", "annulled")
INVOICE_LINE_SOURCES = ("labor", "part", "manual", "adjustment")


class Invoice(Base, TimestampMixin):
    """docs/01 §Invoice: Draft -> Issued -> (Annulled). This slice only ever
    creates Draft rows — issue/annul/reissue are a later slice."""

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_orders.id"), index=True)
    status: Mapped[str] = mapped_column(default="draft", server_default="draft")
    number: Mapped[int | None] = mapped_column(default=None)
    issued_at: Mapped[datetime | None] = mapped_column(default=None)
    seller: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    buyer: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    vat_mode: Mapped[str | None] = mapped_column(default=None)
    net: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    vat: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    gross: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    currency: Mapped[str] = mapped_column(default="EUR", server_default="EUR")
    annuls_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id"), default=None
    )
    annul_reason: Mapped[str | None] = mapped_column(default=None)
    pdf_storage_key: Mapped[str | None] = mapped_column(default=None)
    row_version: Mapped[int] = mapped_column(default=1, server_default="1")


class InvoiceLine(Base):
    """One billable line on a draft invoice — prefilled from order part/labor
    lines at creation (source="part"/"labor"), or added manually while still
    a draft (source="manual"/"adjustment")."""

    __tablename__ = "invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    description: Mapped[str]
    qty: Mapped[int] = mapped_column(default=1, server_default="1")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default="0")
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    source: Mapped[str]
    sort: Mapped[int] = mapped_column(default=0, server_default="0")


class Payment(Base):
    """Unified payment/refund record (docs/01 §Payment): one mechanism for
    deposits, partial payments and refunds. Corrections are new offsetting
    records — a Payment is never mutated or deleted once recorded."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_orders.id"), index=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id"), default=None
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    method: Mapped[str]
    is_refund: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str] = mapped_column(default="", server_default="")
    received_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    received_at: Mapped[datetime]
