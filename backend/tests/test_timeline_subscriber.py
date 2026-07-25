"""BOS-09 Q8 safety fix: the timeline subscriber reacts only to an explicit
allowlist of ServiceFlow event types, not to "any event with a subject_id" -
so a non-ServiceFlow event (e.g. a future professional_services one) can
carry a subject_id that is not a service_orders id without the subscriber
attempting to write it into TimelineEvent.order_id (FK'd to service_orders
only) and raising a foreign-key violation."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from business_os.shared_kernel.events import DomainEvent
from serviceflow.timeline.service import _record


class _DbThatMustNotBeTouched:
    """Standing in for a Session: if `_record` reaches `db.add(...)`, this
    raises immediately - proving the event was rejected before any write
    was attempted, with no database required to prove it."""

    def add(self, _obj: object) -> None:
        raise AssertionError("_record must not touch the session for an unknown event type")


def test_non_serviceflow_event_is_ignored() -> None:
    event = DomainEvent(
        type="ps_stage_changed",  # not in KNOWN_EVENT_TYPES
        company_id=uuid.uuid4(), actor_user_id=uuid.uuid4(),
        subject_id=uuid.uuid4(),  # a plausible-looking id that is not a service_orders row
        data={"from_stage_id": str(uuid.uuid4()), "to_stage_id": str(uuid.uuid4())},
    )

    _record(_DbThatMustNotBeTouched(), event)  # must not raise, must not touch db.add


def test_event_with_no_subject_is_still_ignored() -> None:
    event = DomainEvent(type="task_created", company_id=uuid.uuid4(), actor_user_id=None)
    _record(_DbThatMustNotBeTouched(), event)


@pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)
def test_known_serviceflow_event_still_writes_timeline_entry(client: TestClient) -> None:
    """A real, known ServiceFlow event type still reaches TimelineEvent -
    the allowlist restricts, it does not silently break the existing path."""
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.timeline.models import TimelineEvent

    company_id = None
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        company_id = seed_company(db, "Сервиз Таймлайн", "Owner", "tl@tl.bg", "парола-123").id

    me = client.post("/api/v1/auth/login",
                     json={"email": "tl@tl.bg", "password": "парола-123"}).json()
    h = {"X-CSRF-Token": str(me["csrf_token"])}
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": "0888111222"}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone", "field_values": {"brand": "Apple"},
    }).json()["id"]
    oid = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x",
    }).json()["id"]

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        assert company_id is not None
        bind_tenant_scope(db, company_id)
        event = db.query(TimelineEvent).filter_by(
            order_id=oid, event_type="order_created",
        ).first()
        assert event is not None
