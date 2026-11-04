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

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id


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
    # Wave 3 Issues 21/26/27: mileage belongs to the visit, not just the
    # asset master record — captured at intake. `created_at` (TimestampMixin)
    # is the visit timestamp; no separate mileage date column. Always
    # optional at the column level (legacy rows, and any order, may be
    # NULL) — Cleanup batch Issue 26 once required it for automotive_repair
    # companies specifically; order-workflow-revamp WP-D (Q9) reversed that,
    # migration 0035.
    mileage: Mapped[int | None] = mapped_column(default=None)
    # Q10 (WP-D): true when `mileage` is lower than the asset's previously
    # recorded maximum and an Owner explicitly confirmed the reading is
    # correct as read (never a system-applied correction) — the reading
    # itself is stored exactly as given, this is purely a display flag.
    # Always False unless that exact bypass path was taken.
    mileage_confirmed_lower: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"),
    )
    # Wave 5 Issue 12: the smallest order-level logistics model. "pickup" or
    # "courier" (validated at the Pydantic layer, same no-DB-CHECK precedent
    # as `priority` above — not a lifecycle field like part_lines.state, so
    # no transition matrix, no constraint). `delivery_address` is a plain
    # copy taken at order-creation time (prefilled from the customer's own
    # `Customer.delivery_address` when present) — independent of that
    # customer field from the moment it's copied, the same "never a live
    # reference" discipline completion_snapshot/Invoice.buyer already use,
    # just without the "frozen at a later event" timing since there's
    # nothing to freeze here: it's fixed by construction, not by a later step.
    delivery_method: Mapped[str | None] = mapped_column(default=None)
    delivery_address: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    origin_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_orders.id"), default=None
    )
    status_changed_at: Mapped[datetime | None] = mapped_column(default=None)
    # Terminal bookkeeping: reason (OQ-2), when, and where we came from (BR-2 unlock).
    terminal_reason: Mapped[str | None] = mapped_column(default=None)
    terminal_at: Mapped[datetime | None] = mapped_column(default=None)
    prev_status_code: Mapped[str | None] = mapped_column(default=None)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    # Wave 4 Issue 7: independent, frozen-at-delivery JSON — same discipline
    # as commercial.Invoice.seller/.buyer (never a live reference into
    # Customer/Company/Asset/line rows, so a later edit to any of them can
    # never retroactively change what a reprinted delivery protocol shows).
    # Built once by service.change_status() the moment the order becomes
    # "delivered"; never rewritten afterward. NULL for every order that has
    # never been delivered, and for orders delivered before this column
    # existed — the delivery-protocol endpoint treats both cases identically
    # (protocol unavailable), never reconstructing from live data.
    completion_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
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
    """Lightweight — no inventory, no reservations in V1 (discovery S5).

    order-workflow-revamp WP-I (Q12/Q13, ADR-BOS-013): a new line is created
    only from a `catalog.CatalogItem` — `name`/`unit_cost`/`unit_price` below
    are the **snapshot** taken at add-time (BR-3: a later catalog price
    change never retroactively changes an existing line). `catalog_item_id`
    is nullable because every line that existed before this migration has no
    catalog item to point to and stays that way forever (Q13c) — it is never
    required to be non-NULL, not even for new lines (the FK is informational/
    traceability only; the service layer, not a NOT NULL constraint, is what
    actually enforces "catalog-only" for lines created after this change)."""

    __tablename__ = "part_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_orders.id"), index=True)
    catalog_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalog_items.id"), default=None,
    )
    name: Mapped[str]
    code: Mapped[str | None] = mapped_column(default=None)
    qty: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default=text("0"))
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=0, server_default=text("0")
    )
    # order-workflow-revamp WP-J (Q15/Q15b, #27): three states — издадена
    # ("issued", from the shop's own supply, available now), поръчана
    # ("ordered", must be ordered in from a supplier), монтирана
    # ("installed"). Replaces Wave 2 Issue 33's 2-state model (migration
    # 0022: needed/received/removed folded into "ordered"); "ordered" and
    # "installed" keep their exact meaning and literal DB value from that
    # model unchanged — only a third value is added, so migration 0038 needs
    # no data backfill, just a widened CHECK constraint. Still no inventory
    # tracking (docs/01: no InventoryItem in V1) — "issued" is a line state
    # only, never a stock movement.
    state: Mapped[str] = mapped_column(default="issued", server_default="issued")
    # order-workflow-revamp WP-J (Q14/Q14b/Q14c, #26): a plain yes/no flag —
    # does not affect price (Q14b), defaults on (Q14c). Replaces Wave 4's
    # `warranty_days` months-at-the-boundary field entirely; the shop's
    # warranty *term* is no longer stored per-line — it is the company-wide
    # text already frozen into the delivery protocol's "Гаранционни условия"
    # section (protocol.py), so there is nothing new to look up here. A
    # protocol snapshot frozen before this migration still carries the old
    # `warranty_days` shape in its own immutable JSON (Q14c: "already-issued
    # protocols keep printing their stored months") — protocol.py's
    # `build_delivery_protocol_data` is what reads both shapes; this column
    # only ever produces the new one.
    has_warranty: Mapped[bool] = mapped_column(default=True, server_default=text("true"))


class LaborLine(Base):
    """Priced from the catalog — per operation (unit="pcs") or per hour
    (unit="hour", Q12d). Same catalog/snapshot discipline as PartLine above —
    see its docstring."""

    __tablename__ = "labor_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_orders.id"), index=True)
    catalog_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalog_items.id"), default=None,
    )
    description: Mapped[str]
    code: Mapped[str | None] = mapped_column(default=None)
    # "pcs" for every pre-WP-I line (backfilled by migration 0037 — they were
    # all fixed-price) and for every new fixed-price catalog item; "hour" only
    # for a new line created from an hourly catalog item.
    unit: Mapped[str] = mapped_column(default="pcs", server_default="pcs")
    # Decimal, not int (ADR-BOS-013 §8): hourly labor needs a fractional qty
    # (1.5 ч.) — a fixed-price ("pcs") line still just uses a whole number.
    qty: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("1"), server_default=text("1"),
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=0, server_default=text("0")
    )
    # Owner-only visibility (enforced at the API layer), NULL on every line
    # added before this migration — no cost data was ever captured for labor.
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    duration_min: Mapped[int | None] = mapped_column(default=None)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class OrderAdjustment(Base):
    """order-workflow-revamp WP-I (Q13, resolves docs/01 OQ-5): the only way
    to correct an order's price ("направи го 50 €") — a signed amount with a
    mandatory reason, Owner-only (enforced at the API layer), append-only (no
    update/delete path — a wrong adjustment is corrected by adding an
    offsetting one, same discipline as `commercial.Payment`). Feeds
    `lines.order_totals()` and becomes a `source="adjustment"` line on an
    invoice draft created from this order (`service_orders.contracts.
    get_order_lines`)."""

    __tablename__ = "order_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_orders.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    reason: Mapped[str]
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class AccessoryItem(Base):
    """Belongs to the order, not the asset — accompanies one intake event."""

    __tablename__ = "accessory_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_orders.id"), index=True)
    name: Mapped[str]
    qty: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    returned: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
