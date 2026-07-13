"""Service orders per docs/01 (aggregate) and docs/08. RLS-covered.

Diagnosis, PartLine, LaborLine, AccessoryItem are IN the ServiceOrder aggregate
(docs/01 §4) — they change together under the same order-level invariants.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from serviceflow.shared_kernel.db import Base, TimestampMixin
from serviceflow.shared_kernel.ids import new_id


class OrderStatus(Base):
    """Global seed: code + kind + default BG name (per-company rename in Етап 3)."""

    __tablename__ = "order_statuses"

    code: Mapped[str] = mapped_column(primary_key=True)
    kind: Mapped[str]
    name_bg: Mapped[str]
    sort: Mapped[int]


class DocumentSequence(Base):
    """Per-company sequential numbering (orders now; gapless invoices in Етап 4)."""

    __tablename__ = "document_sequences"
    __table_args__ = (
        Index("uq_document_sequences_key", "company_id", "kind", "year", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    kind: Mapped[str]
    year: Mapped[int]
    current: Mapped[int] = mapped_column(BigInteger, default=0, server_default=text("0"))


class ServiceOrder(Base, TimestampMixin):
    __tablename__ = "service_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    number: Mapped[str]  # "2026-00042", unique per company (index in migration)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id"), index=True)
    complaint: Mapped[str]
    status_code: Mapped[str] = mapped_column(ForeignKey("order_statuses.code"), index=True)
    technician_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    priority: Mapped[str] = mapped_column(default="normal", server_default="normal")
    promised_on: Mapped[date | None] = mapped_column(default=None)
    warranty_days: Mapped[int | None] = mapped_column(default=None)
    origin_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_orders.id"), default=None
    )
    status_changed_at: Mapped[datetime | None] = mapped_column(default=None)
    # Terminal bookkeeping: reason (OQ-2), when, and where we came from (BR-2 unlock).
    terminal_reason: Mapped[str | None] = mapped_column(default=None)
    terminal_at: Mapped[datetime | None] = mapped_column(default=None)
    prev_status_code: Mapped[str | None] = mapped_column(default=None)
    delivered_at: Mapped[datetime | None] = mapped_column(default=None)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    archived_at: Mapped[datetime | None] = mapped_column(default=None)
    row_version: Mapped[int] = mapped_column(default=1, server_default=text("1"))


class Diagnosis(Base, TimestampMixin):
    """0..1 per order (docs/01 §Diagnosis); edited in place, no versioning —
    every edit is timeline-recorded by the service layer, not by this model."""

    __tablename__ = "diagnoses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_orders.id"), unique=True
    )
    observed: Mapped[str] = mapped_column(default="", server_default="")
    cause: Mapped[str] = mapped_column(default="", server_default="")
    recommendation: Mapped[str] = mapped_column(default="", server_default="")
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    estimated_days: Mapped[int | None] = mapped_column(default=None)
    repairable: Mapped[bool | None] = mapped_column(default=None)
    approval_required: Mapped[bool] = mapped_column(default=False)
    # {approved: bool, by_user: str, at: iso str, channel: str, amount: number}
    approval: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)


class PartLine(Base):
    """Lightweight — no inventory, no reservations in V1 (discovery S5)."""

    __tablename__ = "part_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_orders.id"), index=True)
    name: Mapped[str]
    qty: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default=text("0"))
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=0, server_default=text("0")
    )
    state: Mapped[str] = mapped_column(default="needed", server_default="needed")


class LaborLine(Base):
    """Fixed-price lines (discovery §5.5) — the model this shop actually prices by."""

    __tablename__ = "labor_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_orders.id"), index=True)
    description: Mapped[str]
    qty: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=0, server_default=text("0")
    )
    duration_min: Mapped[int | None] = mapped_column(default=None)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class AccessoryItem(Base):
    """Belongs to the order, not the asset — accompanies one intake event."""

    __tablename__ = "accessory_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_orders.id"), index=True)
    name: Mapped[str]
    qty: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    returned: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
