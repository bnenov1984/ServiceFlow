"""Asset endpoints per docs/09: /asset-types, /customers/{id}/assets, /assets/{id}.

`asset_type_code` stays the wire-level identifier (docs/business-os/18 §15) —
clients send/receive the same string ("phone", "vehicle", ...) as before this
module's asset types became company-scoped; only the internal storage
(`Asset.asset_type_id`, a UUID FK) changed. Every handler below resolves
between the two at the boundary.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from business_os.identity.deps import (
    TenantDbDep,
    TenantDep,
    require_csrf,
    require_subscription_ok,
)
from serviceflow.assets import service
from serviceflow.assets.models import Asset, AssetType
from serviceflow.customers import service as customers_service

router = APIRouter()


class AssetTypeOut(BaseModel):
    code: str
    name_bg: str
    icon: str
    field_defs: list[dict[str, Any]]


class AssetIn(BaseModel):
    asset_type_code: str = Field(min_length=1, max_length=50)
    field_values: dict[str, Any] = Field(default_factory=dict)


class AssetPatch(BaseModel):
    field_values: dict[str, Any] = Field(default_factory=dict)


class AssetOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    asset_type_code: str
    label: str
    field_values: dict[str, Any]
    archived: bool
    row_version: int
    duplicate_asset_ids: list[uuid.UUID] = []

    @staticmethod
    def of(a: Asset, asset_type_code: str,
          duplicates: list[uuid.UUID] | None = None) -> "AssetOut":
        return AssetOut(
            id=a.id, customer_id=a.customer_id, asset_type_code=asset_type_code,
            label=a.label, field_values=a.field_values,
            archived=a.archived_at is not None, row_version=a.row_version,
            duplicate_asset_ids=duplicates or [],
        )


def _err(status: int, code: str, key: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={
        "code": code, "message_key": key, "params": {}, **extra,
    })


@router.get("/asset-types")
def list_asset_types(db: TenantDbDep, tenant: TenantDep) -> list[AssetTypeOut]:
    return [AssetTypeOut(code=t.code, name_bg=t.name_bg, icon=t.icon,
                         field_defs=t.field_defs) for t in service.list_types(db, tenant)]


@router.get("/customers/{customer_id}/assets")
def list_customer_assets(customer_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep,
                         include_archived: bool = False) -> list[AssetOut]:
    if customers_service.get(db, tenant, customer_id) is None:
        raise _err(404, "not_found", "errors.customers.not_found")
    assets = service.list_for_customer(db, tenant, customer_id, include_archived)
    # One lookup for the whole list (a handful of types per company) rather
    # than one query per asset.
    codes_by_id = {t.id: t.code for t in service.list_types(db, tenant)}
    return [AssetOut.of(a, codes_by_id[a.asset_type_id]) for a in assets]


@router.post("/customers/{customer_id}/assets",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
             status_code=201)
def create_asset(customer_id: uuid.UUID, body: AssetIn, db: TenantDbDep,
                 tenant: TenantDep) -> AssetOut:
    if customers_service.get(db, tenant, customer_id) is None:
        raise _err(404, "not_found", "errors.customers.not_found")
    asset_type = service.get_type_by_code(db, tenant, body.asset_type_code)
    if asset_type is None:
        raise _err(400, "unknown_asset_type", "errors.assets.unknown_type")
    try:
        asset, duplicates = service.create(db, tenant, customer_id, asset_type,
                                           body.field_values)
    except service.FieldValidationError as e:
        raise _err(400, "field_validation", "errors.assets.invalid_fields",
                   field_errors=e.field_errors) from e
    return AssetOut.of(asset, asset_type.code, duplicates)


def _get_or_404(db: TenantDbDep, tenant: TenantDep, asset_id: uuid.UUID) -> Asset:
    asset = service.get(db, tenant, asset_id)
    if asset is None:
        raise _err(404, "not_found", "errors.assets.not_found")
    return asset


def _type_or_500(db: TenantDbDep, tenant: TenantDep, asset: Asset) -> AssetType:
    asset_type = service.get_type_by_id(db, tenant, asset.asset_type_id)
    assert asset_type is not None, (
        "an asset's own asset_type_id must always resolve within its own "
        "company — the FK guarantees this at the database level"
    )
    return asset_type


@router.get("/assets/{asset_id}")
def get_asset(asset_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> AssetOut:
    asset = _get_or_404(db, tenant, asset_id)
    return AssetOut.of(asset, _type_or_500(db, tenant, asset).code)


@router.patch("/assets/{asset_id}",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def patch_asset(asset_id: uuid.UUID, body: AssetPatch, db: TenantDbDep,
                tenant: TenantDep) -> AssetOut:
    asset = _get_or_404(db, tenant, asset_id)
    asset_type = _type_or_500(db, tenant, asset)
    try:
        asset, duplicates = service.update_fields(db, tenant, asset, asset_type,
                                                  body.field_values)
    except service.FieldValidationError as e:
        raise _err(400, "field_validation", "errors.assets.invalid_fields",
                   field_errors=e.field_errors) from e
    return AssetOut.of(asset, asset_type.code, duplicates)


@router.post("/assets/{asset_id}/archive",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def archive_asset(asset_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> AssetOut:
    asset = _get_or_404(db, tenant, asset_id)
    asset_type = _type_or_500(db, tenant, asset)
    service.archive(db, asset)
    return AssetOut.of(asset, asset_type.code)
