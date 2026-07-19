"""Asset operations: typed-field validation against seed defs, identifier extraction."""

import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.normalize import normalize_identifier
from serviceflow.assets.models import Asset, AssetIdentifier, AssetType


class FieldValidationError(Exception):
    def __init__(self, field_errors: list[dict[str, str]]) -> None:
        self.field_errors = field_errors


def list_types(db: Session) -> list[AssetType]:
    return list(db.scalars(select(AssetType).order_by(AssetType.sort)))


def get_type(db: Session, code: str) -> AssetType | None:
    return db.get(AssetType, code)


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
        asset_type_code=asset_type.code, label=_label(asset_type, cleaned),
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
