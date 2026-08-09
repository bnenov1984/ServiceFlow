"""Customer endpoints per docs/09 §customers."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from business_os.identity.deps import (
    TenantDbDep,
    TenantDep,
    require_csrf,
    require_owner,
    require_repairflow_active,
    require_subscription_ok,
)
from business_os.shared_kernel.normalize import (
    is_valid_eik,
    is_valid_vat_number,
    normalize_eik,
    normalize_vat_number,
)
from serviceflow.customers import service
from serviceflow.customers.models import Customer
from serviceflow.service_orders import service as orders_service

router = APIRouter(dependencies=[Depends(require_repairflow_active)])


class CustomerCompanyRequisites(BaseModel):
    """Buyer-company legal requisites for a future Invoice.buyer snapshot
    (docs/ACCOUNTANT_REVIEW.md §4 B1, LAW-CONFIRMED core list) — replaces
    the previously fully-unconstrained `dict[str, Any]`; `extra="forbid"`
    is the allow-list enforcement point, same pattern as the seller-side
    `CompanyRequisitesPatch`. `vat_number` (Customer VAT Identity
    prerequisite slice) is the buyer-side counterpart to R2's law-confirmed
    "BG" + ЕИК seller VAT number — explicitly entered, never derived/
    auto-generated from `eik` alone, since a company's VAT-registration
    status is a fact this module cannot infer (see
    `customers/service.py`'s `_validate_vat_identity`)."""

    model_config = ConfigDict(extra="forbid")

    address: str | None = Field(default=None, max_length=500)
    eik: str | None = Field(default=None, max_length=20)
    vat_number: str | None = Field(default=None, max_length=20)

    @field_validator("eik")
    @classmethod
    def _validate_eik(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_eik(value)
        if not normalized:
            return None
        if not is_valid_eik(normalized):
            raise ValueError("invalid EIK/BULSTAT: expected 9 or 13 digits")
        return normalized

    @field_validator("vat_number")
    @classmethod
    def _validate_vat_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_vat_number(value)
        if not normalized:
            return None
        if not is_valid_vat_number(normalized):
            raise ValueError('invalid VAT number: expected "BG" + 9 or 13 digits')
        return normalized


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=3, max_length=30)
    phone2: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    is_company: bool = False
    # Tri-state, default None/unknown (never False) — a Customer VAT
    # Identity prerequisite slice concern, not something this create
    # payload is expected to resolve on its own. See Customer.vat_registered.
    vat_registered: bool | None = None
    company_requisites: CustomerCompanyRequisites | None = None
    notes: str = Field(default="", max_length=5000)


class CustomerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, min_length=3, max_length=30)
    phone2: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    is_company: bool | None = None
    vat_registered: bool | None = None
    company_requisites: CustomerCompanyRequisites | None = None
    notes: str | None = Field(default=None, max_length=5000)


class CustomerOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    phone2: str | None
    email: str | None
    is_company: bool
    vat_registered: bool | None
    company_requisites: CustomerCompanyRequisites | None
    notes: str
    archived: bool
    anonymized: bool
    row_version: int
    duplicate_ids: list[uuid.UUID] = []

    @staticmethod
    def of(c: Customer, duplicate_ids: list[uuid.UUID] | None = None) -> "CustomerOut":
        # Built via .get() rather than **c.company_requisites so a read
        # never breaks on an unexpected stored key — it's dropped from the
        # response, not deleted from the row (matches _company_requisites_out's
        # established defensive-read pattern on the Company/seller side).
        raw = c.company_requisites or None
        requisites = (
            CustomerCompanyRequisites(
                address=raw.get("address"), eik=raw.get("eik"), vat_number=raw.get("vat_number"),
            )
            if raw else None
        )
        return CustomerOut(
            id=c.id, name=c.name, phone=c.phone, phone2=c.phone2, email=c.email,
            is_company=c.is_company, vat_registered=c.vat_registered,
            company_requisites=requisites,
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


def _customer_error(e: service.CustomerError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": "customer_error", "message_key": e.message_key, "params": {},
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
    try:
        customer = service.create(db, tenant, **body.model_dump())
    except service.CustomerError as e:
        raise _customer_error(e) from e
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
    try:
        customer = service.update(db, tenant, customer, fields)
    except service.CustomerError as e:
        raise _customer_error(e) from e
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
