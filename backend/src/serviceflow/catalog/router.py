"""Catalog endpoints per docs/09 §catalog (ADR-BOS-013, order-workflow-revamp
WP-I). Reads are open to any active user (the line picker needs them);
every mutation — create/update/archive/unarchive/import — is Owner-only
(Q12b)."""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from business_os.identity.deps import (
    TenantDbDep,
    TenantDep,
    require_csrf,
    require_owner,
    require_repairflow_active,
    require_subscription_ok,
)
from serviceflow.catalog import service
from serviceflow.catalog.models import CatalogItem

router = APIRouter(dependencies=[Depends(require_repairflow_active)])

# Every mutation here is Owner-only (Q12b) and subscription-gated, same as
# every other mutating endpoint in the app — one shared list so each route
# declaration stays within the line-length limit.
_OWNER_MUTATE = [Depends(require_csrf), Depends(require_owner), Depends(require_subscription_ok)]


class CatalogItemOut(BaseModel):
    id: uuid.UUID
    kind: str
    name: str
    code: str | None
    unit: str
    sale_price: float
    # Owner-only visibility — `list_items` below passes include_cost=True
    # only for an Owner caller, never trusting a client-side filter.
    unit_cost: float | None
    archived: bool

    @staticmethod
    def of(i: CatalogItem, *, include_cost: bool) -> "CatalogItemOut":
        return CatalogItemOut(
            id=i.id, kind=i.kind, name=i.name, code=i.code, unit=i.unit,
            sale_price=float(i.sale_price),
            unit_cost=float(i.unit_cost) if include_cost and i.unit_cost is not None else None,
            archived=i.archived_at is not None,
        )


class CatalogItemIn(BaseModel):
    kind: str = Field(pattern="^(part|labor)$")
    name: str = Field(min_length=1, max_length=300)
    code: str | None = Field(default=None, max_length=100)
    unit: str = Field(pattern="^(pcs|hour)$")
    sale_price: Decimal = Field(ge=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)


class CatalogItemPatch(BaseModel):
    kind: str | None = Field(default=None, pattern="^(part|labor)$")
    name: str | None = Field(default=None, min_length=1, max_length=300)
    code: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, pattern="^(pcs|hour)$")
    sale_price: Decimal | None = Field(default=None, ge=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)


class ImportRowOut(BaseModel):
    row_number: int
    action: str
    kind: str
    name: str
    code: str | None
    unit: str
    sale_price: str
    unit_cost: str | None
    error: str | None

    @staticmethod
    def of(r: service.ImportRow) -> "ImportRowOut":
        return ImportRowOut(
            row_number=r.row_number, action=r.action, kind=r.kind, name=r.name,
            code=r.code, unit=r.unit, sale_price=r.sale_price, unit_cost=r.unit_cost,
            error=r.error,
        )


class ImportResultOut(BaseModel):
    rows: list[ImportRowOut]
    insert_count: int
    update_count: int
    error_count: int

    @staticmethod
    def of(r: service.ImportResult) -> "ImportResultOut":
        return ImportResultOut(
            rows=[ImportRowOut.of(row) for row in r.rows], insert_count=r.insert_count,
            update_count=r.update_count, error_count=r.error_count,
        )


def _err(e: service.CatalogError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": "catalog_error", "message_key": e.message_key, "params": {},
    })


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "code": "not_found", "message_key": "errors.catalog.not_found", "params": {},
    })


def _conflict(existing_id: uuid.UUID) -> HTTPException:
    return HTTPException(status_code=409, detail={
        "code": "code_conflict", "message_key": "errors.catalog.code_conflict",
        "params": {}, "conflicting_item_id": str(existing_id),
    })


@router.get("/catalog-items")
def list_items(db: TenantDbDep, tenant: TenantDep, kind: str | None = None,
               include_archived: bool = False) -> list[CatalogItemOut]:
    items = service.list_items(db, tenant, kind=kind, include_archived=include_archived)
    return [CatalogItemOut.of(i, include_cost=tenant.is_owner) for i in items]


@router.post("/catalog-items",
            dependencies=_OWNER_MUTATE, status_code=201)
def create_item(body: CatalogItemIn, db: TenantDbDep, tenant: TenantDep) -> CatalogItemOut:
    try:
        item = service.create(
            db, tenant, kind=body.kind, name=body.name, unit=body.unit,
            sale_price=body.sale_price, code=body.code, unit_cost=body.unit_cost,
        )
    except service.CatalogError as e:
        raise _err(e) from e
    except service.CodeConflictError as e:
        raise _conflict(e.existing_item_id) from e
    return CatalogItemOut.of(item, include_cost=True)


@router.patch("/catalog-items/{item_id}",
             dependencies=_OWNER_MUTATE)
def patch_item(item_id: uuid.UUID, body: CatalogItemPatch, db: TenantDbDep,
               tenant: TenantDep) -> CatalogItemOut:
    item = service.get(db, tenant, item_id)
    if item is None:
        raise _not_found()
    try:
        item = service.update(db, tenant, item, body.model_dump(exclude_unset=True))
    except service.CatalogError as e:
        raise _err(e) from e
    except service.CodeConflictError as e:
        raise _conflict(e.existing_item_id) from e
    return CatalogItemOut.of(item, include_cost=True)


@router.post("/catalog-items/{item_id}/archive",
            dependencies=_OWNER_MUTATE)
def archive_item(item_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> CatalogItemOut:
    item = service.get(db, tenant, item_id)
    if item is None:
        raise _not_found()
    service.archive(db, item)
    return CatalogItemOut.of(item, include_cost=True)


@router.post("/catalog-items/{item_id}/unarchive",
            dependencies=_OWNER_MUTATE)
def unarchive_item(item_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> CatalogItemOut:
    item = service.get(db, tenant, item_id)
    if item is None:
        raise _not_found()
    service.unarchive(db, item)
    return CatalogItemOut.of(item, include_cost=True)


# --- CSV/Excel import (Q12b) -------------------------------------------------

@router.post("/catalog-items/import/preview",
            dependencies=_OWNER_MUTATE)
def preview_import(db: TenantDbDep, tenant: TenantDep,
                   file: Annotated[UploadFile, File()]) -> ImportResultOut:
    data = file.file.read()  # sync read — same precedent as attachments.router's upload
    result = service.preview_import(db, tenant, data, file.filename or "")
    return ImportResultOut.of(result)


@router.post("/catalog-items/import/commit",
            dependencies=_OWNER_MUTATE)
def commit_import(db: TenantDbDep, tenant: TenantDep,
                  file: Annotated[UploadFile, File()]) -> ImportResultOut:
    data = file.file.read()
    result = service.commit_import(db, tenant, data, file.filename or "")
    return ImportResultOut.of(result)
