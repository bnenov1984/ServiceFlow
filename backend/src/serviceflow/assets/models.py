"""Assets per docs/01: generic Asset + per-company AssetType (no form builder, S2).

AssetType is company-scoped RepairFlow business-profile data (ADR-BOS-011
§Decision 5, docs/business-os/18 §6.4/§15) — every company owns its own copy,
seeded once at provisioning (`serviceflow.assets.service.seed_default_types`,
triggered by the `company_provisioned` domain event). A later edit to one
company's copy never touches another's; there is no shared template to fork
from at all, unlike PS workflow templates which still have one.
Asset and AssetIdentifier are tenant tables under RLS; AssetType now is too.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id


class AssetType(Base, TimestampMixin):
    """`business_profile` tags which RepairFlow profile this copy was seeded
    under (ADR-BOS-011's five-slug vocabulary — validated by the caller,
    `platform_admin.service.VALID_BUSINESS_PROFILES`, not here, same
    division of labor as `identity.service.set_business_profile`). Each
    profile now seeds its own single type with its own field_defs
    (order-workflow-revamp WP-C, Q18, migration 0034) — the column exists so
    a future profile needs only a branch in `seed_default_types`, never
    another schema change."""

    __tablename__ = "asset_types"
    __table_args__ = (
        Index("uq_asset_types_company_id_code", "company_id", "code", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    code: Mapped[str]
    business_profile: Mapped[str]
    name_bg: Mapped[str]
    icon: Mapped[str] = mapped_column(default="", server_default="")
    sort: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    # [{key, label_bg, type: text|number|date|choice, choices?, identifier_kind?}]
    field_defs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'")
    )
    # order-workflow-revamp WP-H (Q16/Q16b, migration 0036): false only for
    # automotive's "vehicle" type — hides the accessories checklist at
    # intake/order/completion for that type without deleting anything;
    # historic AccessoryItem rows and old protocols/snapshots keep rendering
    # regardless (see serviceflow.service_orders.protocol, which only
    # renders the section when there's a non-empty list to show).
    accessories: Mapped[bool] = mapped_column(default=True, server_default=text("true"))


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    asset_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asset_types.id"))
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
    indexes (ADR-010, docs/08 §assets).

    VIN is the one kind with a hard uniqueness rule (Wave 3 Issue 20, migration
    0023's partial unique index on (company_id, value_normalized) WHERE
    kind='vin') — one normalized VIN identifies exactly one vehicle Asset per
    tenant. IMEI/serial/рег.№ keep the original soft-duplicate-hint behavior
    (`assets.service.find_duplicates_by_identifiers`) unchanged."""

    __tablename__ = "asset_identifiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str]  # imei | serial | vin | reg | other
    value: Mapped[str]
    value_normalized: Mapped[str] = mapped_column(index=True)


class AssetOwnership(Base):
    """Append-only ownership-span history per Asset (Wave 3 Issue 20).

    `Asset.customer_id` remains the current-owner pointer (unchanged);
    `ServiceOrder.asset_id`/`.customer_id` already need no change of their
    own — an order already correctly records which customer walked in that
    day, and asset_id already correctly identifies the one persistent
    vehicle regardless of who owned it then. This table only adds the
    missing piece: a queryable "who owned this asset, and when" history, so
    an ownership change never has to duplicate the Asset row to represent a
    new owner (see `serviceflow.assets.service.transfer_owner`).

    At most one row per asset has `ended_at IS NULL` (the current span) —
    enforced by migration 0023's partial unique index
    `uq_asset_ownership_open`, not just by convention."""

    __tablename__ = "asset_ownership"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime | None] = mapped_column(default=None)
