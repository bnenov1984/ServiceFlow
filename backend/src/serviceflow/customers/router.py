"""Customer endpoints per docs/09 §customers."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

# Wave 5 Issue 11: BG-specific structural validation (EIK, "BG"+EIK VAT
# shape) only applies when country == this. Every other country is accepted
# as an opaque, manually-entered identifier — no per-country tax validation
# in this Wave (explicitly out of scope; see docs/business-os Wave 5 audit).
_BG = "BG"


class CustomerCompanyRequisites(BaseModel):
    """Buyer-company legal requisites for a future Invoice.buyer snapshot
    (docs/ACCOUNTANT_REVIEW.md §4 B1, LAW-CONFIRMED core list) — replaces
    the previously fully-unconstrained `dict[str, Any]`; `extra="forbid"`
    is the allow-list enforcement point, same pattern as the seller-side
    `CompanyRequisitesPatch`. `vat_number` is auto-derived (Wave 5) only
    when `country == "BG"`, `vat_registered` is explicitly True, and `eik`
    is structurally valid — see `customers/service.py`'s
    `_derive_bg_vat_number`; the VAT-registration status itself is still
    never inferred from `eik` alone.

    `country` (Wave 5 Issue 11/12): ISO 3166-1 alpha-2, defaults to "BG" —
    every company customer created before this field existed only ever was
    Bulgarian, so a stored blob with no "country" key reads back as "BG"
    (see CustomerOut.of), never rewritten to add the key."""

    model_config = ConfigDict(extra="forbid")

    country: str = Field(default=_BG, pattern="^[A-Z]{2}$")
    address: str | None = Field(default=None, max_length=500)
    eik: str | None = Field(default=None, max_length=20)
    vat_number: str | None = Field(default=None, max_length=20)

    @field_validator("eik")
    @classmethod
    def _normalize_eik_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_eik(value) or None

    @field_validator("vat_number")
    @classmethod
    def _normalize_vat_number_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_vat_number(value) or None

    @model_validator(mode="after")
    def _validate_bg_identifiers(self) -> "CustomerCompanyRequisites":
        # Structural EIK/VAT-shape checks are BG-specific (docs/
        # ACCOUNTANT_REVIEW.md §3 R1/R2) — a foreign company's identifier is
        # accepted as typed, normalized (trimmed) only, never format-checked
        # against a rule that was never true for it.
        if self.country != _BG:
            return self
        if self.eik is not None and not is_valid_eik(self.eik):
            raise ValueError("invalid EIK/BULSTAT: expected 9 or 13 digits")
        if self.vat_number is not None and not is_valid_vat_number(self.vat_number):
            raise ValueError('invalid VAT number: expected "BG" + 9 or 13 digits')
        return self


class CustomerDeliveryAddress(BaseModel):
    """Wave 5 Issue 12: ONE optional default delivery address — individual
    or company customer alike, independent of company_requisites.address
    (the registered/legal address). No address history."""

    model_config = ConfigDict(extra="forbid")

    address: str = Field(min_length=1, max_length=500)


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
    # order-workflow-revamp WP-B (Q20): an individual's own optional main
    # address — free-text, multi-line (newlines are just characters in a
    # str, no separate "multi-line" validation needed). Meaningful only for
    # is_company=False; a company's main address is company_requisites.address.
    address: str | None = Field(default=None, max_length=1000)
    delivery_address: CustomerDeliveryAddress | None = None
    notes: str = Field(default="", max_length=5000)


class CustomerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, min_length=3, max_length=30)
    phone2: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    is_company: bool | None = None
    vat_registered: bool | None = None
    company_requisites: CustomerCompanyRequisites | None = None
    address: str | None = Field(default=None, max_length=1000)
    delivery_address: CustomerDeliveryAddress | None = None
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
    address: str | None
    delivery_address: CustomerDeliveryAddress | None
    notes: str
    archived: bool
    anonymized: bool
    row_version: int

    @staticmethod
    def of(c: Customer) -> "CustomerOut":
        # Built via .get() rather than **c.company_requisites so a read
        # never breaks on an unexpected stored key — it's dropped from the
        # response, not deleted from the row (matches _company_requisites_out's
        # established defensive-read pattern on the Company/seller side).
        raw = c.company_requisites or None
        requisites = (
            CustomerCompanyRequisites(
                # Wave 5: absent "country" (every pre-Wave-5 row) reads as
                # "BG" — the only country this product ever supported before
                # this field existed, never a migration/backfill.
                country=raw.get("country") or _BG,
                address=raw.get("address"), eik=raw.get("eik"), vat_number=raw.get("vat_number"),
            )
            if raw else None
        )
        raw_delivery = c.delivery_address or None
        delivery_address = (
            CustomerDeliveryAddress(address=raw_delivery["address"])
            if raw_delivery and raw_delivery.get("address") else None
        )
        return CustomerOut(
            id=c.id, name=c.name, phone=c.phone, phone2=c.phone2, email=c.email,
            is_company=c.is_company, vat_registered=c.vat_registered,
            company_requisites=requisites, address=c.address, delivery_address=delivery_address,
            notes=c.notes, archived=c.archived_at is not None,
            anonymized=c.anonymized_at is not None, row_version=c.row_version,
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


class DuplicateCheckOut(BaseModel):
    """order-workflow-revamp WP-B (Q7/Q8): the inline-on-blur pre-check — a
    convenience the UI calls before submit so the rejection can be shown as
    a field-level error rather than only after a round trip through POST/
    PATCH. Never the enforcement point itself; service.create()/update()
    independently re-check and are what actually blocks a save (this
    endpoint is read-only, no CSRF/subscription gate needed)."""

    duplicate: "DuplicateCustomerOut | None"


class DuplicateCustomerOut(BaseModel):
    id: uuid.UUID
    name: str


@router.get("/phone-check")
def check_phone(phone: str, db: TenantDbDep, tenant: TenantDep) -> DuplicateCheckOut:
    match = service.find_duplicate_individual_by_phone(db, tenant, phone)
    return DuplicateCheckOut(
        duplicate=DuplicateCustomerOut(id=match.id, name=match.name) if match else None,
    )


@router.get("/eik-check")
def check_eik(eik: str, db: TenantDbDep, tenant: TenantDep) -> DuplicateCheckOut:
    match = service.find_duplicate_company_by_eik(db, tenant, normalize_eik(eik))
    return DuplicateCheckOut(
        duplicate=DuplicateCustomerOut(id=match.id, name=match.name) if match else None,
    )


@router.post("", dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
            status_code=201)
def create_customer(body: CustomerIn, db: TenantDbDep, tenant: TenantDep) -> CustomerOut:
    try:
        customer = service.create(db, tenant, **body.model_dump())
    except service.CustomerError as e:
        raise _customer_error(e) from e
    return CustomerOut.of(customer)


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
    return CustomerOut.of(customer)


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
