"""Customer endpoints per docs/09 §customers."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from business_os.identity.deps import (
    TenantDbDep,
    TenantDep,
    require_csrf,
    require_owner,
    require_subscription_ok,
)
from serviceflow.customers import service
from serviceflow.customers.models import Customer
from serviceflow.service_orders import service as orders_service

router = APIRouter()


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=3, max_length=30)
    phone2: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    is_company: bool = False
    company_requisites: dict[str, Any] | None = None
    notes: str = Field(default="", max_length=5000)


class CustomerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, min_length=3, max_length=30)
    phone2: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    is_company: bool | None = None
    company_requisites: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=5000)


class CustomerOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    phone2: str | None
    email: str | None
    is_company: bool
    company_requisites: dict[str, Any] | None
    notes: str
    archived: bool
    anonymized: bool
    row_version: int
    duplicate_ids: list[uuid.UUID] = []

    @staticmethod
    def of(c: Customer, duplicate_ids: list[uuid.UUID] | None = None) -> "CustomerOut":
        return CustomerOut(
            id=c.id, name=c.name, phone=c.phone, phone2=c.phone2, email=c.email,
            is_company=c.is_company, company_requisites=c.company_requisites,
            notes=c.notes, archived=c.archived_at is not None,
            anonymized=c.anonymized_at is not None, row_version=c.row_version,
            duplicate_ids=duplicate_ids or [],
        )


class CustomerListItemOut(CustomerOut):
    """GET /customers only — adds the active-order count the list row needs
    (docs/15 §6.7) without touching CustomerOut's other callers."""
    active_orders_count: int


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "code": "not_found", "message_key": "errors.customers.not_found", "params": {},
    })


@router.get("")
def list_customers(db: TenantDbDep, tenant: TenantDep, q: str | None = None,
                   include_archived: bool = False) -> list[CustomerListItemOut]:
    customers = service.search(db, tenant, q, include_archived)
    counts = orders_service.count_active_by_customer(db, tenant, (c.id for c in customers))
    return [
        CustomerListItemOut(
            **CustomerOut.of(c).model_dump(), active_orders_count=counts.get(c.id, 0),
        )
        for c in customers
    ]


@router.post("", dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
            status_code=201)
def create_customer(body: CustomerIn, db: TenantDbDep, tenant: TenantDep) -> CustomerOut:
    # Duplicate phones warn, never block (docs/02 B3): the hint rides on the response.
    duplicates = service.find_duplicates_by_phone(db, tenant, body.phone)
    customer = service.create(db, tenant, **body.model_dump())
    return CustomerOut.of(customer, [d.id for d in duplicates])


@router.get("/{customer_id}")
def get_customer(customer_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> CustomerOut:
    customer = service.get(db, tenant, customer_id)
    if customer is None:
        raise _not_found()
    return CustomerOut.of(customer)


@router.patch("/{customer_id}",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def patch_customer(customer_id: uuid.UUID, body: CustomerPatch, db: TenantDbDep,
                   tenant: TenantDep) -> CustomerOut:
    customer = service.get(db, tenant, customer_id)
    if customer is None:
        raise _not_found()
    if customer.anonymized_at is not None:
        raise HTTPException(status_code=409, detail={
            "code": "anonymized", "message_key": "errors.customers.anonymized", "params": {},
        })
    fields = body.model_dump(exclude_unset=True)
    customer = service.update(db, tenant, customer, fields)
    duplicates = (
        service.find_duplicates_by_phone(db, tenant, customer.phone, exclude_id=customer.id)
        if "phone" in fields else []
    )
    return CustomerOut.of(customer, [d.id for d in duplicates])


@router.post("/{customer_id}/archive",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def archive_customer(customer_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> CustomerOut:
    customer = service.get(db, tenant, customer_id)
    if customer is None:
        raise _not_found()
    service.archive(db, tenant, customer)
    return CustomerOut.of(customer)


@router.post("/{customer_id}/anonymize",
             dependencies=[Depends(require_csrf), Depends(require_owner),
                          Depends(require_subscription_ok)])
def anonymize_customer(customer_id: uuid.UUID, db: TenantDbDep,
                       tenant: TenantDep) -> CustomerOut:
    customer = service.get(db, tenant, customer_id)
    if customer is None:
        raise _not_found()
    service.anonymize(db, tenant, customer)
    return CustomerOut.of(customer)
