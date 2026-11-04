"""Tasks: order-bound and company-level, completion/reopen rules, cross-order views,
tenant isolation. Deliberately outside the ServiceOrder aggregate (docs/01 §4)."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _login(client: TestClient, company: str = "Сервиз А",
           email: str = "a@a.bg") -> dict[str, str]:
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, company, "Owner", email, "парола-123")
    me = client.post("/api/v1/auth/login",
                     json={"email": email, "password": "парола-123"}).json()
    return {"X-CSRF-Token": str(me["csrf_token"])}


def _order(client: TestClient, h: dict[str, str]) -> str:
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": "0888111222"}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]
    return str(client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "x",
    }).json()["id"])


def test_company_level_task_needs_no_order(client: TestClient) -> None:
    h = _login(client)
    r = client.post("/api/v1/tasks", headers=h, json={"title": "Поръчай консумативи"})
    assert r.status_code == 201
    assert r.json()["order_id"] is None
    assert r.json()["is_done"] is False


def test_order_bound_task_create_complete_writes_timeline(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    r = client.post(f"/api/v1/orders/{oid}/tasks", headers=h,
                    json={"title": "Обади се на клиента", "is_call": True})
    assert r.status_code == 201
    tid = r.json()["id"]

    r = client.patch(f"/api/v1/tasks/{tid}", headers=h, json={"is_done": True})
    assert r.status_code == 200
    assert r.json()["is_done"] is True
    assert r.json()["completed_at"] is not None

    events = [e["event_type"] for e in client.get(f"/api/v1/orders/{oid}/timeline").json()]
    assert "task_created" in events
    assert "task_completed" in events


def test_completion_never_changes_order_status(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    tid = client.post(f"/api/v1/orders/{oid}/tasks", headers=h,
                      json={"title": "x"}).json()["id"]
    client.patch(f"/api/v1/tasks/{tid}", headers=h, json={"is_done": True})
    assert client.get(f"/api/v1/orders/{oid}").json()["status_code"] == "received"


def test_reopen_blocked_when_order_is_terminal(client: TestClient) -> None:
    h = _login(client)
    oid = _order(client, h)
    tid = client.post(f"/api/v1/orders/{oid}/tasks", headers=h,
                      json={"title": "x"}).json()["id"]
    client.patch(f"/api/v1/tasks/{tid}", headers=h, json={"is_done": True})
    client.post(f"/api/v1/orders/{oid}/status", headers=h,
               json={"to": "cancelled", "reason": "дубликат"})

    r = client.patch(f"/api/v1/tasks/{tid}", headers=h, json={"is_done": False})
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.tasks.order_terminal"


def test_reassign_uses_explicit_flag_to_allow_unassign(client: TestClient) -> None:
    h = _login(client)
    tid = client.post("/api/v1/tasks", headers=h, json={"title": "x"}).json()["id"]

    from business_os.identity import security
    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        from sqlalchemy import select
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        worker = User(company_id=owner.company_id, name="Иво", email="ivo@a.bg",
                      password_hash=security.hash_secret("x"))
        db.add(worker)
        db.commit()
        worker_id = str(worker.id)

    r = client.patch(f"/api/v1/tasks/{tid}", headers=h,
                     json={"assign": True, "assignee_id": worker_id})
    assert r.status_code == 200
    assert r.json()["assignee_id"] == worker_id

    r = client.patch(f"/api/v1/tasks/{tid}", headers=h, json={"assign": True})
    assert r.status_code == 200
    assert r.json()["assignee_id"] is None


def test_cross_order_views_today_mine_calls(client: TestClient) -> None:
    import datetime as dt

    h = _login(client)
    now = dt.datetime.now(dt.UTC)  # server computes "today" in UTC, not local wall-clock
    today = now.date().isoformat()
    yesterday = (now.date() - dt.timedelta(days=1)).isoformat()
    future = (now.date() + dt.timedelta(days=30)).isoformat()

    client.post("/api/v1/tasks", headers=h, json={"title": "due today", "due_on": today})
    client.post("/api/v1/tasks", headers=h,
               json={"title": "overdue", "due_on": yesterday})
    client.post("/api/v1/tasks", headers=h, json={"title": "future", "due_on": future})
    client.post("/api/v1/tasks", headers=h, json={"title": "call me", "is_call": True})

    today_titles = {t["title"] for t in client.get("/api/v1/tasks?today=true").json()}
    assert today_titles == {"due today", "overdue"}

    call_titles = {t["title"] for t in client.get("/api/v1/tasks?calls=true").json()}
    assert call_titles == {"call me"}


def test_tasks_are_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    oid = _order(client, h_a)
    tid = client.post(f"/api/v1/orders/{oid}/tasks", headers=h_a,
                      json={"title": "x"}).json()["id"]
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    assert client.get("/api/v1/tasks").json() == []
    assert client.patch(f"/api/v1/tasks/{tid}", headers=h_b,
                        json={"is_done": True}).status_code == 404
