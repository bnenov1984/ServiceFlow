"""Customer operations. Every query goes through scoped() (ADR-016 chokepoint);
RLS is the second net underneath."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from serviceflow.customers.models import Customer
from serviceflow.shared_kernel.db import TenantContext, scoped
from serviceflow.shared_kernel.normalize import normalize_phone, transliterate


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
    customer = Customer(company_id=ctx.company_id, **fields)
    _refresh_shadows(customer)
    db.add(customer)
    db.commit()
    return customer


def get(db: Session, ctx: TenantContext, customer_id: uuid.UUID) -> Customer | None:
    return db.scalar(
        scoped(select(Customer), Customer, ctx).where(Customer.id == customer_id)
    )


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
    _refresh_shadows(customer)
    customer.anonymized_at = datetime.now(UTC)
    customer.archived_at = customer.archived_at or customer.anonymized_at
    db.commit()
