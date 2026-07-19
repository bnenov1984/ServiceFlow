"""Professional Services walking skeleton: module-gate 404, tenant isolation,
and the end-to-end client -> assignment -> next action journey."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _seed(company: str, email: str, activate: bool = True) -> None:
    from business_os.identity.service import activate_module, seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        row = seed_company(db, company, "Мария", email, "парола-123")
        if activate:
            activate_module(db, row.id, "professional-services")


def _login(client: TestClient, email: str) -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "парола-123"})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def test_routes_404_when_module_inactive(client: TestClient) -> None:
    _seed("Сервиз Неактивен", "inactive@ps.bg", activate=False)
    _login(client, "inactive@ps.bg")

    resp = client.get("/api/v1/ps/clients")
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.ps.module_inactive"


def test_full_journey_client_assignment_next_action(client: TestClient) -> None:
    import datetime

    _seed("Сервиз ПС", "ps@ps.bg")
    me = _login(client, "ps@ps.bg")
    csrf = str(me["csrf_token"])
    headers = {"X-CSRF-Token": csrf}

    resp = client.post("/api/v1/ps/clients", json={"name": "Инвест ЕООД", "kind": "company"},
                       headers=headers)
    assert resp.status_code == 200, resp.text
    client_id = resp.json()["id"]

    resp = client.post(
        "/api/v1/ps/assignments",
        json={"client_id": client_id, "title": "Годишен преглед"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assignment = resp.json()
    assert assignment["stage"] == "intake"

    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    resp = client.post(
        "/api/v1/ps/next-actions",
        json={
            "assignment_id": assignment["id"], "title": "Обаждане на клиента",
            "owner_user_id": me["user_id"], "due_on": yesterday,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    action = resp.json()
    assert action["risk"] == "overdue"
    assert action["completed"] is False

    resp = client.post(f"/api/v1/ps/assignments/{assignment['id']}/stage",
                       json={"to": "in_progress"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["stage"] == "in_progress"

    resp = client.post(f"/api/v1/ps/next-actions/{action['id']}/complete", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["completed"] is True
    assert resp.json()["risk"] == "done"

    resp = client.get(f"/api/v1/ps/assignments/{assignment['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Годишен преглед"


def test_cross_tenant_isolation(client: TestClient) -> None:
    import uuid

    _seed("Сервиз А ПС", "a-ps@ps.bg")
    _seed("Сервиз Б ПС", "b-ps@ps.bg")

    me_a = _login(client, "a-ps@ps.bg")
    csrf_a = str(me_a["csrf_token"])
    resp = client.post("/api/v1/ps/clients", json={"name": "Клиент А"},
                       headers={"X-CSRF-Token": csrf_a})
    client_a_id = resp.json()["id"]

    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_a})
    _login(client, "b-ps@ps.bg")

    # Company B must never see company A's client, even by guessed id.
    resp = client.get(f"/api/v1/ps/clients/{client_a_id}")
    assert resp.status_code == 404

    resp = client.get("/api/v1/ps/clients")
    assert resp.json() == []

    # And a fully random id is equally invisible (not a signal either way).
    resp = client.get(f"/api/v1/ps/clients/{uuid.uuid4()}")
    assert resp.status_code == 404
