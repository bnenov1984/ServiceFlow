"""Assets per docs/01: generic Asset + seed-defined AssetType (no form builder, S2).

AssetType is system reference data — global, seeded by migration, no tenant scope.
Asset and AssetIdentifier are tenant tables under RLS.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id


class AssetType(Base):
    __tablename__ = "asset_types"

    code: Mapped[str] = mapped_column(primary_key=True)
    name_bg: Mapped[str]
    icon: Mapped[str] = mapped_column(default="", server_default="")
    sort: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    # [{key, label_bg, type: text|number|date|choice, choices?, identifier_kind?}]
    field_defs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'")
    )


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    asset_type_code: Mapped[str] = mapped_column(ForeignKey("asset_types.code"))
    label: Mapped[str]  # display: brand + model or explicit label
    field_values: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
    # Reserved for encrypted sensitive fields (device passcodes, 11 §5) — wired later.
    sensitive_values: Mapped[bytes | None] = mapped_column(default=None)
    archived_at: Mapped[datetime | None] = mapped_column(default=None)
    row_version: Mapped[int] = mapped_column(default=1, server_default=text("1"))


class AssetIdentifier(Base):
    """Searchable identifiers (IMEI/VIN/serial/рег.№) extracted from field_values
    on every save — real columns because search and duplicate hints need real
    indexes (ADR-010, docs/08 §assets)."""

    __tablename__ = "asset_identifiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str]  # imei | serial | vin | reg | other
    value: Mapped[str]
    value_normalized: Mapped[str] = mapped_column(index=True)
