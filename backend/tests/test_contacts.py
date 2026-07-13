"""ContactRecord: communication channels + the "note" type extension, author-only
edit window until end of day (OQ-1 default), tenant isolation."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _login(client: TestClient, company: str = "Сервиз А",
           email: str = "a@a.bg") -> dict[str, str]:
    from serviceflow.identity.service import seed_company
    from serviceflow.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, company, "Owner", email, "парола-123")
    me = client.post("/api/v1/auth/login",
                     json={"email": email, "password": "парола-123"}).json()
    return {"X-CSRF-Token": str(me["csrf_token"])}


def _customer(client: TestClient, h: dict[str, str]) -> str:
    return str(client.post("/api/v1/customers", headers=h,
                           json={"name": "Иван", "phone": "0888111222"}).json()["id"])


def _order(client: TestClient, h: dict[str, str], cid: str) -> str:
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone", "field_values": {"brand": "Apple"},
    }).json()["id"]
    return str(client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x",
    }).json()["id"])


def test_communication_type_requires_direction(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    r = client.post(f"/api/v1/customers/{cid}/contact-records", headers=h,
                    json={"type": "call", "summary": "Обади се клиентът"})
    assert r.status_code == 400
    assert r.json()["detail"]["message_key"] == "errors.contacts.direction_required"

    r = client.post(f"/api/v1/customers/{cid}/contact-records", headers=h,
                    json={"type": "call", "direction": "in", "summary": "Обади се клиентът"})
    assert r.status_code == 201
    assert r.json()["direction"] == "in"


def test_note_type_has_no_direction(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    r = client.post(f"/api/v1/customers/{cid}/contact-records", headers=h,
                    json={"type": "note", "summary": "Клиентът предпочита вечерни часове"})
    assert r.status_code == 201
    assert r.json()["direction"] is None
    assert r.json()["type"] == "note"


def test_order_bound_note_derives_customer_and_writes_timeline(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    oid = _order(client, h, cid)

    r = client.post(f"/api/v1/orders/{oid}/contact-records", headers=h,
                    json={"type": "note", "summary": "Трябва да проверим гаранцията"})
    assert r.status_code == 201
    assert r.json()["customer_id"] == cid
    assert r.json()["order_id"] == oid

    events = [e["event_type"] for e in client.get(f"/api/v1/orders/{oid}/timeline").json()]
    assert "note_or_contact_recorded" in events


def test_visible_from_both_order_and_customer_views(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    oid = _order(client, h, cid)
    client.post(f"/api/v1/orders/{oid}/contact-records", headers=h,
               json={"type": "visit", "direction": "in", "summary": "Дойде да пита"})

    order_view = client.get(f"/api/v1/orders/{oid}/contact-records").json()
    customer_view = client.get(f"/api/v1/customers/{cid}/contact-records").json()
    assert len(order_view) == 1
    assert len(customer_view) == 1
    assert order_view[0]["id"] == customer_view[0]["id"]


def test_edit_allowed_for_author_before_frozen(client: TestClient) -> None:
    h = _login(client)
    cid = _customer(client, h)
    rid = client.post(f"/api/v1/customers/{cid}/contact-records", headers=h,
                      json={"type": "note", "summary": "първоначален текст"}).json()["id"]

    r = client.patch(f"/api/v1/contact-records/{rid}", headers=h,
                     json={"summary": "поправен текст"})
    assert r.status_code == 200
    assert r.json()["summary"] == "поправен текст"
    assert r.json()["editable"] is True


def test_edit_blocked_once_frozen(client: TestClient) -> None:
    import os as _os

    from serviceflow.identity.service import seed_company
    from serviceflow.shared_kernel.db import open_session

    for db in open_session(_os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, "Сервиз А", "Owner", "a@a.bg", "парола-123")
    me = client.post("/api/v1/auth/login",
                     json={"email": "a@a.bg", "password": "парола-123"}).json()
    h = {"X-CSRF-Token": str(me["csrf_token"])}

    cid = _customer(client, h)

    # Backdate occurred_at to yesterday so frozen_after (end of that day) has passed.
    import datetime as dt
    yesterday_noon = (dt.datetime.now(dt.UTC) - dt.timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    rid = client.post(f"/api/v1/customers/{cid}/contact-records", headers=h, json={
        "type": "note", "summary": "стара бележка",
        "occurred_at": yesterday_noon.isoformat(),
    }).json()["id"]

    r = client.get(f"/api/v1/customers/{cid}/contact-records").json()[0]
    assert r["editable"] is False

    r = client.patch(f"/api/v1/contact-records/{rid}", headers=h,
                     json={"summary": "опит за редакция"})
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.contacts.frozen"


def test_edit_blocked_for_non_author(client: TestClient) -> None:
    from serviceflow.identity import security
    from serviceflow.identity.models import User
    from serviceflow.shared_kernel.db import open_session

    h = _login(client)
    cid = _customer(client, h)
    rid = client.post(f"/api/v1/customers/{cid}/contact-records", headers=h,
                      json={"type": "note", "summary": "бележка от Мария"}).json()["id"]

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        from sqlalchemy import select
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        worker = User(company_id=owner.company_id, name="Иво", email="ivo@a.bg",
                      password_hash=security.hash_secret("x"))
        db.add(worker)
        db.commit()

    r = client.post("/api/v1/auth/login", json={"email": "ivo@a.bg", "password": "x"})
    h_worker = {"X-CSRF-Token": r.json()["csrf_token"]}

    r = client.patch(f"/api/v1/contact-records/{rid}", headers=h_worker,
                     json={"summary": "чужда редакция"})
    assert r.status_code == 403
    assert r.json()["detail"]["message_key"] == "errors.contacts.not_author"


def test_contacts_are_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    cid = _customer(client, h_a)
    rid = client.post(f"/api/v1/customers/{cid}/contact-records", headers=h_a,
                      json={"type": "note", "summary": "x"}).json()["id"]
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    assert client.get(f"/api/v1/customers/{cid}/contact-records").status_code == 404
    assert client.patch(f"/api/v1/contact-records/{rid}", headers=h_b,
                        json={"summary": "y"}).status_code == 404
