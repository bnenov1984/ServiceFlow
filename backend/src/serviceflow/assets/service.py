"""Asset operations: typed-field validation against seed defs, identifier extraction,
company-scoped asset-type seeding (ADR-BOS-011 §Decision 5).
"""

import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, bind_tenant_scope, scoped
from business_os.shared_kernel.events import DomainEvent, subscribe
from business_os.shared_kernel.normalize import normalize_identifier
from serviceflow.assets.models import Asset, AssetIdentifier, AssetType

# Identical to migration 0015's frozen SEED_TYPES copy (migrations never
# import application code, so that copy and this one are deliberately kept
# in sync by hand, not shared) — this is the runtime source `seed_default_types`
# reads for every company provisioned *after* that migration ran; the
# migration itself backfilled every company that existed before it.
DEFAULT_TYPES: list[dict[str, Any]] = [
    {
        "code": "phone", "name_bg": "Телефон", "icon": "smartphone", "sort": 1,
        "field_defs": [
            {"key": "brand", "label_bg": "Марка", "type": "text"},
            {"key": "model", "label_bg": "Модел", "type": "text"},
            {"key": "imei", "label_bg": "IMEI", "type": "text", "identifier_kind": "imei"},
            {"key": "serial_no", "label_bg": "Сериен №", "type": "text",
             "identifier_kind": "serial"},
            {"key": "color", "label_bg": "Цвят", "type": "text"},
        ],
    },
    {
        "code": "vehicle", "name_bg": "Автомобил", "icon": "car", "sort": 2,
        "field_defs": [
            {"key": "brand", "label_bg": "Марка", "type": "text"},
            {"key": "model", "label_bg": "Модел", "type": "text"},
            {"key": "reg_no", "label_bg": "Рег. №", "type": "text", "identifier_kind": "reg"},
            {"key": "vin", "label_bg": "VIN", "type": "text", "identifier_kind": "vin"},
            {"key": "year", "label_bg": "Година", "type": "number"},
            {"key": "mileage", "label_bg": "Пробег (км)", "type": "number"},
        ],
    },
    {
        "code": "laptop", "name_bg": "Лаптоп/Компютър", "icon": "laptop", "sort": 3,
        "field_defs": [
            {"key": "brand", "label_bg": "Марка", "type": "text"},
            {"key": "model", "label_bg": "Модел", "type": "text"},
            {"key": "serial_no", "label_bg": "Сериен №", "type": "text",
             "identifier_kind": "serial"},
        ],
    },
    {
        "code": "other", "name_bg": "Друго", "icon": "wrench", "sort": 4,
        "field_defs": [
            {"key": "description", "label_bg": "Описание", "type": "text"},
            {"key": "identifier", "label_bg": "Идентификатор", "type": "text",
             "identifier_kind": "other"},
        ],
    },
]

# Mirrors identity.service.DEFAULT_BUSINESS_PROFILE ("generic_repair") without
# importing identity for one string — assets is a vertical, so importing Core
# would be allowed, but this constant is small and stable enough that a
# documented duplicate is simpler than the coupling (same call this codebase
# already made for "generic_repair" appearing as a literal in ADR-BOS-011,
# docs/business-os/18, and platform_admin.service.DEFAULT_BUSINESS_PROFILE).
_FALLBACK_BUSINESS_PROFILE = "generic_repair"


class FieldValidationError(Exception):
    def __init__(self, field_errors: list[dict[str, str]]) -> None:
        self.field_errors = field_errors


def list_types(db: Session, ctx: TenantContext) -> list[AssetType]:
    return list(db.scalars(
        scoped(select(AssetType), AssetType, ctx).order_by(AssetType.sort)
    ))


def get_type_by_code(db: Session, ctx: TenantContext, code: str) -> AssetType | None:
    return db.scalar(scoped(select(AssetType), AssetType, ctx).where(AssetType.code == code))


def get_type_by_id(db: Session, ctx: TenantContext,
                   asset_type_id: uuid.UUID) -> AssetType | None:
    return db.scalar(scoped(select(AssetType), AssetType, ctx).where(
        AssetType.id == asset_type_id
    ))


def seed_default_types(db: Session, company_id: uuid.UUID, business_profile: str) -> None:
    """Seeds this company's own copy of the current asset-type set
    (ADR-BOS-011 §Decision 5, copy-on-provisioning — same discipline
    `professional_services.assignments.service.create_assignment` already
    established for workflow-template stages). Every profile currently seeds
    identical content (docs/business-os/18 §15) — `business_profile` is
    stored on each row regardless, so a future profile-specific set is a
    branch here, not a schema change. Non-committing — the caller (the
    `company_provisioned` subscriber below, itself called from inside
    `ProvisionCompany`'s/`seed_company`'s own transaction) commits."""
    for t in DEFAULT_TYPES:
        db.add(AssetType(
            company_id=company_id, code=t["code"], name_bg=t["name_bg"],
            icon=t["icon"], sort=t["sort"], field_defs=t["field_defs"],
            business_profile=business_profile,
        ))


@subscribe
def _seed_types_on_company_provisioned(db: Session, event: DomainEvent) -> None:
    """Reacts to `company_provisioned` (published by
    `business_os.identity.service.seed_company` and
    `business_os.platform_admin.service.provision_company`) rather than
    either of those Core modules importing `serviceflow.assets` directly,
    which `core-not-modules`/`vendor-plane-not-tenant-code`
    (backend/.importlinter) forbid — the same synchronous, same-transaction
    domain-event mechanism `serviceflow.timeline` already uses, applied
    across the Core/vertical edge instead of within ServiceFlow. Registered
    as a side effect of this module being imported (already transitive via
    `serviceflow.assets.router`, itself imported by `serviceflow/main.py`).

    `bind_tenant_scope` is required here, not optional: `asset_types` is
    RLS-protected (FORCE ROW LEVEL SECURITY, no `WITH CHECK` of its own —
    Postgres reuses the `USING` clause for both), but company provisioning
    runs as an RLS-*exempt* identity/vendor operation with no tenant GUC
    bound yet (ADR-016 note). Without this call the seeding INSERT would be
    silently rejected by the very policy this migration added. Harmless to
    the rest of the publisher's transaction: every other table that
    transaction touches (companies, users, platform_admin_* ) is RLS-exempt
    too, so binding the GUC here has no effect on them."""
    if event.type != "company_provisioned":
        return
    bind_tenant_scope(db, event.company_id)
    business_profile = event.data.get("business_profile", _FALLBACK_BUSINESS_PROFILE)
    seed_default_types(db, event.company_id, business_profile)


def validate_field_values(asset_type: AssetType,
                          values: dict[str, Any]) -> dict[str, Any]:
    """Rejects unknown keys and type mismatches; returns the cleaned dict."""
    defs = {d["key"]: d for d in asset_type.field_defs}
    errors: list[dict[str, str]] = []
    cleaned: dict[str, Any] = {}
    for key, raw in values.items():
        d = defs.get(key)
        if d is None:
            errors.append({"loc": key, "type": "unknown_field"})
            continue
        if raw is None or raw == "":
            continue
        ftype = d["type"]
        if ftype == "number" and not isinstance(raw, int | float):
            errors.append({"loc": key, "type": "not_a_number"})
        elif ftype == "date":
            try:
                date.fromisoformat(str(raw))
            except ValueError:
                errors.append({"loc": key, "type": "not_a_date"})
        elif ftype == "choice" and raw not in d.get("choices", []):
            errors.append({"loc": key, "type": "invalid_choice"})
        elif ftype == "text" and not isinstance(raw, str):
            errors.append({"loc": key, "type": "not_text"})
        if not errors or errors[-1].get("loc") != key:
            cleaned[key] = raw
    if errors:
        raise FieldValidationError(errors)
    return cleaned


def _label(asset_type: AssetType, values: dict[str, Any]) -> str:
    brand = str(values.get("brand", "")).strip()
    model = str(values.get("model", "")).strip()
    if brand or model:
        return f"{brand} {model}".strip()
    return str(values.get("description", "")).strip() or asset_type.name_bg


def _extract_identifiers(asset: Asset, asset_type: AssetType) -> list[AssetIdentifier]:
    rows: list[AssetIdentifier] = []
    for d in asset_type.field_defs:
        kind = d.get("identifier_kind")
        if not kind:
            continue
        raw = str(asset.field_values.get(d["key"], "") or "").strip()
        if not raw:
            continue
        rows.append(AssetIdentifier(
            company_id=asset.company_id, asset_id=asset.id, kind=kind,
            value=raw, value_normalized=normalize_identifier(raw),
        ))
    return rows


def find_duplicates_by_identifiers(db: Session, ctx: TenantContext,
                                   identifiers: list[AssetIdentifier],
                                   exclude_asset_id: uuid.UUID | None = None,
                                   ) -> list[uuid.UUID]:
    values = [i.value_normalized for i in identifiers if i.value_normalized]
    if not values:
        return []
    stmt = scoped(select(AssetIdentifier.asset_id), AssetIdentifier, ctx).where(
        AssetIdentifier.value_normalized.in_(values)
    ).distinct()
    if exclude_asset_id is not None:
        stmt = stmt.where(AssetIdentifier.asset_id != exclude_asset_id)
    return list(db.scalars(stmt))


def create(db: Session, ctx: TenantContext, customer_id: uuid.UUID,
           asset_type: AssetType, values: dict[str, Any]) -> tuple[Asset, list[uuid.UUID]]:
    cleaned = validate_field_values(asset_type, values)
    asset = Asset(
        company_id=ctx.company_id, customer_id=customer_id,
        asset_type_id=asset_type.id, label=_label(asset_type, cleaned),
        field_values=cleaned,
    )
    db.add(asset)
    db.flush()
    identifiers = _extract_identifiers(asset, asset_type)
    duplicates = find_duplicates_by_identifiers(db, ctx, identifiers, asset.id)
    db.add_all(identifiers)
    db.commit()
    return asset, duplicates


def get(db: Session, ctx: TenantContext, asset_id: uuid.UUID) -> Asset | None:
    return db.scalar(scoped(select(Asset), Asset, ctx).where(Asset.id == asset_id))


def get_many(db: Session, ctx: TenantContext,
             asset_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Asset]:
    ids = set(asset_ids)
    if not ids:
        return {}
    rows = db.scalars(scoped(select(Asset), Asset, ctx).where(Asset.id.in_(ids)))
    return {a.id: a for a in rows}


def list_for_customer(db: Session, ctx: TenantContext, customer_id: uuid.UUID,
                      include_archived: bool = False) -> list[Asset]:
    stmt = scoped(select(Asset), Asset, ctx).where(Asset.customer_id == customer_id)
    if not include_archived:
        stmt = stmt.where(Asset.archived_at.is_(None))
    return list(db.scalars(stmt.order_by(Asset.created_at)))


def update_fields(db: Session, ctx: TenantContext, asset: Asset,
                  asset_type: AssetType, values: dict[str, Any],
                  ) -> tuple[Asset, list[uuid.UUID]]:
    cleaned = validate_field_values(asset_type, {**asset.field_values, **values})
    asset.field_values = cleaned
    asset.label = _label(asset_type, cleaned)
    asset.row_version += 1
    db.execute(delete(AssetIdentifier).where(AssetIdentifier.asset_id == asset.id))
    identifiers = _extract_identifiers(asset, asset_type)
    duplicates = find_duplicates_by_identifiers(db, ctx, identifiers, asset.id)
    db.add_all(identifiers)
    db.commit()
    return asset, duplicates


def archive(db: Session, asset: Asset) -> None:
    asset.archived_at = datetime.now(UTC)
    db.commit()
