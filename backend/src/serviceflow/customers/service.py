"""Customer operations. Every query goes through scoped() (ADR-016 chokepoint);
RLS is the second net underneath."""

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.normalize import normalize_phone, transliterate
from serviceflow.customers.models import Customer


class CustomerError(Exception):
    def __init__(self, message_key: str, status: int = 400) -> None:
        self.message_key = message_key
        self.status = status


def _validate_vat_identity(is_company: bool, vat_registered: bool | None,
                           company_requisites: dict[str, Any] | None) -> None:
    """docs/ACCOUNTANT_REVIEW.md §4 B1: a company customer explicitly marked
    VAT-registered must carry a VAT number, or a future B2B Issue workflow
    (not built by this slice — see commercial/service.py's still-untouched
    company_buyer_unsupported check) would have nothing to freeze into the
    Invoice.buyer snapshot. Not enforced for is_company=False or
    vat_registered in (None, False) — UNKNOWN and explicitly-not-registered
    are both valid, complete states on their own."""
    if not is_company or vat_registered is not True:
        return
    vat_number = (company_requisites or {}).get("vat_number")
    if not vat_number:
        raise CustomerError("errors.customers.vat_number_required")


def _refresh_shadows(customer: Customer) -> None:
    customer.phone_normalized = normalize_phone(customer.phone)
    customer.name_translit = transliterate(customer.name)


def find_duplicates_by_phone(db: Session, ctx: TenantContext, phone: str,
                             exclude_id: uuid.UUID | None = None) -> list[Customer]:
    normalized = normalize_phone(phone)
    if not normalized:
        return []
    stmt = scoped(select(Customer), Customer, ctx).where(
        Customer.phone_normalized == normalized,
        Customer.archived_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(Customer.id != exclude_id)
    return list(db.scalars(stmt))


def create(db: Session, ctx: TenantContext, **fields: object) -> Customer:
    is_company = fields.get("is_company", False)
    vat_registered = fields.get("vat_registered")
    company_requisites = fields.get("company_requisites")
    assert isinstance(is_company, bool)
    assert vat_registered is None or isinstance(vat_registered, bool)
    assert company_requisites is None or isinstance(company_requisites, dict)
    _validate_vat_identity(is_company, vat_registered, company_requisites)

    customer = Customer(company_id=ctx.company_id, **fields)
    _refresh_shadows(customer)
    db.add(customer)
    db.commit()
    return customer


def get(db: Session, ctx: TenantContext, customer_id: uuid.UUID) -> Customer | None:
    return db.scalar(
        scoped(select(Customer), Customer, ctx).where(Customer.id == customer_id)
    )


def get_many(db: Session, ctx: TenantContext,
             customer_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Customer]:
    ids = set(customer_ids)
    if not ids:
        return {}
    rows = db.scalars(scoped(select(Customer), Customer, ctx).where(Customer.id.in_(ids)))
    return {c.id: c for c in rows}


def search(db: Session, ctx: TenantContext, q: str | None,
           include_archived: bool = False, limit: int = 50) -> list[Customer]:
    stmt = scoped(select(Customer), Customer, ctx)
    if not include_archived:
        stmt = stmt.where(Customer.archived_at.is_(None))
    if q:
        translit_q = transliterate(q)
        phone_q = normalize_phone(q)
        conditions = [Customer.name_translit.contains(translit_q)]
        if phone_q:
            conditions.append(Customer.phone_normalized.contains(phone_q))
        stmt = stmt.where(or_(*conditions))
    stmt = stmt.order_by(Customer.name_translit).limit(limit)
    return list(db.scalars(stmt))


def update(db: Session, ctx: TenantContext, customer: Customer,
           fields: dict[str, object]) -> Customer:
    for key, value in fields.items():
        setattr(customer, key, value)
    # Validated against the merged effective state (existing row + this
    # patch), not the raw patch body alone — a PATCH touching only
    # vat_registered (leaving a previously-stored company_requisites
    # untouched) must still be checked against what the record will
    # actually read as afterward.
    _validate_vat_identity(
        customer.is_company, customer.vat_registered, customer.company_requisites,
    )
    _refresh_shadows(customer)
    customer.row_version += 1
    db.commit()
    return customer


def archive(db: Session, ctx: TenantContext, customer: Customer) -> None:
    customer.archived_at = datetime.now(UTC)
    db.commit()


def anonymize(db: Session, ctx: TenantContext, customer: Customer) -> None:
    """GDPR (docs/11 §6): personal data overwritten, history preserved. Irreversible."""
    customer.name = "Изтрит клиент"
    customer.phone = ""
    customer.phone2 = None
    customer.email = None
    customer.notes = ""
    customer.company_requisites = None
    customer.is_company = False
    customer.vat_registered = None
    _refresh_shadows(customer)
    customer.anonymized_at = datetime.now(UTC)
    customer.archived_at = customer.archived_at or customer.anonymized_at
    db.commit()
