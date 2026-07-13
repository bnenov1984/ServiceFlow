"""BR-5: the timeline is append-only at the database level, not just by convention."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def test_timeline_events_reject_update_and_delete(client: TestClient) -> None:
    from sqlalchemy.exc import ProgrammingError

    from serviceflow.identity.service import seed_company
    from serviceflow.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.timeline.models import TimelineEvent

    company_id = None
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        company_id = seed_company(db, "Сервиз А", "Owner", "a@a.bg", "парола-123").id

    me = client.post("/api/v1/auth/login",
                     json={"email": "a@a.bg", "password": "парола-123"}).json()
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
        event = db.query(TimelineEvent).filter_by(order_id=oid).first()
        assert event is not None

        with pytest.raises(ProgrammingError, match="append-only"):
            event.event_type = "tampered"
            db.commit()
        db.rollback()

        with pytest.raises(ProgrammingError, match="append-only"):
            db.delete(event)
            db.commit()
        db.rollback()
