"""ContactRecord endpoints per docs/09 §contact-records + customer profile needs
(docs/10 §2.4 Комуникация). Order-bound entries derive customer_id from the order."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from business_os.identity.deps import (
    TenantDbDep,
    TenantDep,
    require_csrf,
    require_repairflow_active,
    require_subscription_ok,
)
from serviceflow.contacts import service
from serviceflow.contacts.models import ContactRecord
from serviceflow.customers import service as customers_service
from serviceflow.service_orders import service as orders_service

router = APIRouter(dependencies=[Depends(require_repairflow_active)])


class ContactRecordIn(BaseModel):
    # Wave 2 Issue 34: message/visit narrowed away as *new-entry* options,
    # matching contacts.service.ALL_TYPES — existing historical rows of
    # those types are untouched and still readable, just no longer creatable.
    type: str = Field(pattern="^(call|email|note)$")
    direction: str | None = Field(default=None, pattern="^(in|out)$")
    summary: str = Field(min_length=1, max_length=5000)
    occurred_at: datetime | None = None


class CustomerContactRecordIn(ContactRecordIn):
    order_id: uuid.UUID | None = None


class ContactRecordPatch(BaseModel):
    summary: str = Field(min_length=1, max_length=5000)


class ContactRecordOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    order_id: uuid.UUID | None
    type: str
    direction: str | None
    summary: str
    occurred_at: datetime
    user_id: uuid.UUID
    editable: bool

    @staticmethod
    def of(r: ContactRecord, acting_user_id: uuid.UUID) -> "ContactRecordOut":
        frozen_after = r.frozen_after
        if frozen_after.tzinfo is None:
            frozen_after = frozen_after.replace(tzinfo=UTC)
        editable = r.user_id == acting_user_id and datetime.now(UTC) < frozen_after
        return ContactRecordOut(
            id=r.id, customer_id=r.customer_id, order_id=r.order_id, type=r.type,
            direction=r.direction, summary=r.summary, occurred_at=r.occurred_at,
            user_id=r.user_id, editable=editable,
        )


def _err(e: service.ContactError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": "contact_error", "message_key": e.message_key, "params": {},
    })


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "code": "not_found", "message_key": "errors.contacts.not_found", "params": {},
    })


@router.get("/orders/{order_id}/contact-records")
def list_order_contacts(order_id: uuid.UUID, db: TenantDbDep,
                        tenant: TenantDep) -> list[ContactRecordOut]:
    if orders_service.get(db, tenant, order_id) is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.orders.not_found", "params": {},
        })
    return [ContactRecordOut.of(r, tenant.user_id)
            for r in service.list_for_order(db, tenant, order_id)]


@router.post("/orders/{order_id}/contact-records",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
             status_code=201)
def create_order_contact(order_id: uuid.UUID, body: ContactRecordIn, db: TenantDbDep,
                         tenant: TenantDep) -> ContactRecordOut:
    customer_id = service.order_customer_id(db, tenant, order_id)
    if customer_id is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.orders.not_found", "params": {},
        })
    try:
        record = service.create(
            db, tenant, customer_id=customer_id, order_id=order_id, type_=body.type,
            summary=body.summary, direction=body.direction, occurred_at=body.occurred_at,
        )
    except service.ContactError as e:
        raise _err(e) from e
    return ContactRecordOut.of(record, tenant.user_id)


@router.get("/customers/{customer_id}/contact-records")
def list_customer_contacts(customer_id: uuid.UUID, db: TenantDbDep,
                           tenant: TenantDep) -> list[ContactRecordOut]:
    if customers_service.get(db, tenant, customer_id) is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.customers.not_found", "params": {},
        })
    return [ContactRecordOut.of(r, tenant.user_id)
            for r in service.list_for_customer(db, tenant, customer_id)]


@router.post("/customers/{customer_id}/contact-records",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
             status_code=201)
def create_customer_contact(customer_id: uuid.UUID, body: CustomerContactRecordIn,
                            db: TenantDbDep, tenant: TenantDep) -> ContactRecordOut:
    if customers_service.get(db, tenant, customer_id) is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.customers.not_found", "params": {},
        })
    try:
        record = service.create(
            db, tenant, customer_id=customer_id, order_id=body.order_id, type_=body.type,
            summary=body.summary, direction=body.direction, occurred_at=body.occurred_at,
        )
    except service.ContactError as e:
        raise _err(e) from e
    return ContactRecordOut.of(record, tenant.user_id)


@router.patch("/contact-records/{record_id}",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def patch_contact(record_id: uuid.UUID, body: ContactRecordPatch, db: TenantDbDep,
                  tenant: TenantDep) -> ContactRecordOut:
    record = service.get(db, tenant, record_id)
    if record is None:
        raise _not_found()
    try:
        record = service.update_summary(db, tenant, record, body.summary)
    except service.ContactError as e:
        raise _err(e) from e
    return ContactRecordOut.of(record, tenant.user_id)
