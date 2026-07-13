"""ContactRecord operations. Order-bound records derive customer_id from the order
(docs/01: customer reference is required, order reference is optional — never the
other way round)."""

import uuid
from datetime import UTC, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from serviceflow.contacts.models import ContactRecord
from serviceflow.service_orders.models import ServiceOrder
from serviceflow.shared_kernel.db import TenantContext, scoped
from serviceflow.shared_kernel.events import DomainEvent, publish

COMMUNICATION_TYPES = ("call", "email", "message", "visit")
ALL_TYPES = (*COMMUNICATION_TYPES, "note")


class ContactError(Exception):
    def __init__(self, message_key: str, status: int = 400) -> None:
        self.message_key = message_key
        self.status = status


def _now() -> datetime:
    return datetime.now(UTC)


def _end_of_day(moment: datetime) -> datetime:
    d = moment.astimezone(UTC).date() if moment.tzinfo else moment.date()
    return datetime.combine(d, time.max, tzinfo=UTC)


def create(db: Session, ctx: TenantContext, *, customer_id: uuid.UUID, type_: str,
           summary: str, direction: str | None = None,
           order_id: uuid.UUID | None = None,
           occurred_at: datetime | None = None) -> ContactRecord:
    if type_ not in ALL_TYPES:
        raise ContactError("errors.contacts.invalid_type")
    if type_ in COMMUNICATION_TYPES and direction not in ("in", "out"):
        raise ContactError("errors.contacts.direction_required")
    if type_ == "note":
        direction = None

    when = occurred_at or _now()
    record = ContactRecord(
        company_id=ctx.company_id, customer_id=customer_id, order_id=order_id,
        type=type_, direction=direction, summary=summary, occurred_at=when,
        user_id=ctx.user_id, frozen_after=_end_of_day(when),
    )
    db.add(record)
    db.flush()
    if order_id is not None:
        publish(db, DomainEvent(type="note_or_contact_recorded", company_id=ctx.company_id,
                                actor_user_id=ctx.user_id, order_id=order_id,
                                data={"type": type_, "summary": summary}))
    db.commit()
    return record


def get(db: Session, ctx: TenantContext, record_id: uuid.UUID) -> ContactRecord | None:
    return db.scalar(
        scoped(select(ContactRecord), ContactRecord, ctx).where(ContactRecord.id == record_id)
    )


def list_for_order(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> list[ContactRecord]:
    return list(db.scalars(
        scoped(select(ContactRecord), ContactRecord, ctx)
        .where(ContactRecord.order_id == order_id).order_by(ContactRecord.occurred_at.desc())
    ))


def list_for_customer(db: Session, ctx: TenantContext,
                      customer_id: uuid.UUID) -> list[ContactRecord]:
    return list(db.scalars(
        scoped(select(ContactRecord), ContactRecord, ctx)
        .where(ContactRecord.customer_id == customer_id)
        .order_by(ContactRecord.occurred_at.desc())
    ))


def order_customer_id(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> uuid.UUID | None:
    order = db.scalar(
        scoped(select(ServiceOrder), ServiceOrder, ctx).where(ServiceOrder.id == order_id)
    )
    return order.customer_id if order else None


def update_summary(db: Session, ctx: TenantContext, record: ContactRecord,
                   summary: str) -> ContactRecord:
    """Author-only, until end of day (docs/01 invariant, OQ-1 default accepted)."""
    if record.user_id != ctx.user_id:
        raise ContactError("errors.contacts.not_author", status=403)
    frozen_after = record.frozen_after
    if frozen_after.tzinfo is None:
        frozen_after = frozen_after.replace(tzinfo=UTC)
    if _now() >= frozen_after:
        raise ContactError("errors.contacts.frozen", status=409)
    record.summary = summary
    db.commit()
    return record
