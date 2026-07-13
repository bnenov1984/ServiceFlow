"""Service orders per docs/01 (aggregate) and docs/08. RLS-covered."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
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
