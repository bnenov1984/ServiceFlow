"""GET /search per docs/09 — grouped results, tenant-isolated by construction."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from serviceflow.identity.deps import TenantDbDep, TenantDep
from serviceflow.search import service

router = APIRouter()


class CustomerHitOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str


class OrderHitOut(BaseModel):
    id: uuid.UUID
    number: str
    status_code: str
    customer_name: str


class AssetHitOut(BaseModel):
    id: uuid.UUID
    label: str
    customer_id: uuid.UUID
    customer_name: str
    matched_identifier: str


class SearchOut(BaseModel):
    customers: list[CustomerHitOut]
    orders: list[OrderHitOut]
    assets: list[AssetHitOut]


@router.get("/search")
def global_search(q: str, db: TenantDbDep, tenant: TenantDep) -> SearchOut:
    r = service.global_search(db, tenant, q)
    return SearchOut(
        customers=[CustomerHitOut(**vars(h)) for h in r.customers],
        orders=[OrderHitOut(**vars(h)) for h in r.orders],
        assets=[AssetHitOut(**vars(h)) for h in r.assets],
    )
