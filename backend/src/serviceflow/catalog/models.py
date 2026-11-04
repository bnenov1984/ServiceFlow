"""CatalogItem — the shop's own price list (ADR-BOS-013). Flat, no
categories/variants: an Owner-maintained list of parts and labor services
that order lines are created from (order-workflow-revamp WP-I, Q12).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id

# Q12d: labor items are either hourly (unit="hour", qty in hours) or
# fixed-price (unit="pcs", qty a plain count) — a part is always "pcs".
KINDS = ("part", "labor")
UNITS = ("pcs", "hour")


class CatalogItem(Base, TimestampMixin):
    __tablename__ = "catalog_items"
    __table_args__ = (
        Index("uq_catalog_items_company_id_code", "company_id", "code", unique=True,
             postgresql_where=text("code IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    kind: Mapped[str]
    name: Mapped[str]
    code: Mapped[str | None] = mapped_column(default=None)
    unit: Mapped[str]
    sale_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), server_default=text("0"),
    )
    # Owner-only visibility (enforced at the API layer, not here).
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    # Items are archived, never deleted — order lines keep a snapshot, but
    # also a nullable FK back here (`PartLine.catalog_item_id`/
    # `LaborLine.catalog_item_id`) that must keep resolving.
    archived_at: Mapped[datetime | None] = mapped_column(default=None)
