"""Customer per docs/01 (entity) and docs/08 §customers. First RLS-covered table."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str]
    phone: Mapped[str]
    phone2: Mapped[str | None] = mapped_column(default=None)
    email: Mapped[str | None] = mapped_column(default=None)
    is_company: Mapped[bool] = mapped_column(default=False)
    # order-workflow-revamp WP-B (Q20): an individual's own optional main
    # address, free-text/multi-line. A company's main address lives in
    # company_requisites.address instead (not this column) — the two are
    # deliberately never both meaningful for the same row.
    address: Mapped[str | None] = mapped_column(default=None)
    # Tri-state (docs/ACCOUNTANT_REVIEW.md §4 B1): NULL = not yet established
    # (never treated as "confirmed not registered"), False = explicitly
    # confirmed not VAT-registered, True = explicitly confirmed VAT-
    # registered (requires company_requisites.vat_number — see
    # customers/service.py's _validate_vat_identity). No server default —
    # every pre-existing row reads back NULL, not False (migration 0019).
    vat_registered: Mapped[bool | None] = mapped_column(default=None)
    # Wave 5 Issue 11/12: `country` lives *inside* this existing JSONB blob
    # (key "country", ISO 3166-1 alpha-2, e.g. "BG") — no schema change to
    # add it. A row with no "country" key at all (every pre-Wave-5 company
    # customer) is read back as "BG" by the router's own defaulting, never
    # backfilled: BG was the only country this product ever supported before
    # now, so treating "absent" as "BG" is simply true, not a migration.
    company_requisites: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    # Wave 5 Issue 12: ONE optional default delivery address, individual or
    # company customer alike (unlike company_requisites, never gated by
    # is_company). Same JSONB-bag-with-an-"address"-key shape as
    # company_requisites — {"address": str} — no address-history subsystem.
    delivery_address: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    notes: Mapped[str] = mapped_column(default="", server_default="")
    # Shadow columns (ADR-010) — maintained by the service layer, never by hand.
    phone_normalized: Mapped[str] = mapped_column(index=True)
    name_translit: Mapped[str] = mapped_column(index=True)
    anonymized_at: Mapped[datetime | None] = mapped_column(default=None)
    archived_at: Mapped[datetime | None] = mapped_column(default=None)
    row_version: Mapped[int] = mapped_column(default=1, server_default=text("1"))
