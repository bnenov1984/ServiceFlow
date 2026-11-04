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
    require_repairflow_active,
    require_subscription_ok,
)
from serviceflow.assets import service
from serviceflow.assets.models import Asset, AssetType
from serviceflow.customers import service as customers_service

router = APIRouter(dependencies=[Depends(require_repairflow_active)])


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


class AssetByVinOut(BaseModel):
    """Issue 20 intake lookup: the vehicle plus who currently owns it, so the
    client can decide between "Използвай автомобила" (reuse, no ownership
    change) and "Смени собственик" (transfer) without a second round trip."""

    id: uuid.UUID
    label: str
    asset_type_code: str
    customer_id: uuid.UUID
    customer_name: str


class TransferOwnerIn(BaseModel):
    customer_id: uuid.UUID


class RegCheckOut(BaseModel):
    """Q11's on-blur pre-check for reg-№, same shape/rationale as customers'
    DuplicateCheckOut (WP-B): a convenience the UI calls before submit so
    the conflict can be shown as an inline field error with a direct
    "Избери този автомобил" action — read-only, no CSRF/subscription gate
    needed. Never the enforcement point itself; service.create()/
    update_fields() independently re-check via _check_reg_conflicts and are
    what actually blocks a save."""

    asset_id: uuid.UUID | None = None
    label: str | None = None


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
    except service.VinConflictError as e:
        raise _err(409, "vin_conflict", "errors.assets.vin_conflict",
                   conflicting_asset_id=str(e.existing_asset_id)) from e
    except service.RegConflictError as e:
        raise _err(409, "reg_conflict", "errors.assets.reg_conflict",
                   conflicting_asset_id=str(e.existing_asset_id)) from e
    return AssetOut.of(asset, asset_type.code, duplicates)


@router.get("/assets/by-vin")
def get_asset_by_vin(vin: str, db: TenantDbDep, tenant: TenantDep) -> AssetByVinOut:
    """Issue 20: tenant-wide VIN lookup for intake — must run before a
    vehicle Asset is blindly created, so a car already on file (under any
    customer) is found and offered for reuse/transfer instead of duplicated."""
    asset = service.find_by_vin(db, tenant, vin)
    if asset is None:
        raise _err(404, "not_found", "errors.assets.vin_not_found")
    asset_type = _type_or_500(db, tenant, asset)
    owner = customers_service.get(db, tenant, asset.customer_id)
    assert owner is not None, (
        "an asset's own customer_id must always resolve within its own company"
    )
    return AssetByVinOut(id=asset.id, label=asset.label, asset_type_code=asset_type.code,
                         customer_id=owner.id, customer_name=owner.name)


@router.get("/assets/reg-check")
def check_reg(reg: str, db: TenantDbDep, tenant: TenantDep,
              exclude_asset_id: uuid.UUID | None = None) -> RegCheckOut:
    asset = service.find_by_reg(db, tenant, reg, exclude_asset_id)
    if asset is None:
        return RegCheckOut()
    return RegCheckOut(asset_id=asset.id, label=asset.label)


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
    except service.VinConflictError as e:
        raise _err(409, "vin_conflict", "errors.assets.vin_conflict",
                   conflicting_asset_id=str(e.existing_asset_id)) from e
    except service.RegConflictError as e:
        raise _err(409, "reg_conflict", "errors.assets.reg_conflict",
                   conflicting_asset_id=str(e.existing_asset_id)) from e
    return AssetOut.of(asset, asset_type.code, duplicates)


@router.post("/assets/{asset_id}/archive",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def archive_asset(asset_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> AssetOut:
    asset = _get_or_404(db, tenant, asset_id)
    asset_type = _type_or_500(db, tenant, asset)
    service.archive(db, asset)
    return AssetOut.of(asset, asset_type.code)


@router.post("/assets/{asset_id}/transfer-owner",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def transfer_owner(asset_id: uuid.UUID, body: TransferOwnerIn, db: TenantDbDep,
                   tenant: TenantDep) -> AssetOut:
    """Issue 20's explicit "Смени собственик" action. Both the asset and the
    new customer are resolved through tenant-scoped lookups (`_get_or_404`,
    `customers_service.get`) — a customer_id from another tenant simply
    doesn't resolve (404), which is what makes cross-tenant transfer
    impossible without a dedicated check."""
    asset = _get_or_404(db, tenant, asset_id)
    asset_type = _type_or_500(db, tenant, asset)
    if customers_service.get(db, tenant, body.customer_id) is None:
        raise _err(404, "not_found", "errors.customers.not_found")
    asset = service.transfer_owner(db, tenant, asset, body.customer_id)
    return AssetOut.of(asset, asset_type.code)
