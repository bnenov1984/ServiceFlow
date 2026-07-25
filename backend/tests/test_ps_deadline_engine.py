"""Professional Services deadline/staleness engine (PS-13, ADR-PS-008):
persisted risk result, the reasoned deadline-change chokepoint and its
append-only history, and the idempotent per-tenant evaluation job."""

import datetime
import os
import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _seed(company: str, email: str, activate: bool = True) -> uuid.UUID:
    from business_os.identity.service import activate_module, seed_company
    from business_os.shared_kernel.db import open_session

    company_id: uuid.UUID | None = None
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        row = seed_company(db, company, "Мария", email, "парола-123")
        company_id = row.id
        if activate:
            activate_module(db, row.id, "professional-services")
    assert company_id is not None
    return company_id


def _login(client: TestClient, email: str) -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "парола-123"})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _headers(me: dict[str, object]) -> dict[str, str]:
    return {"X-CSRF-Token": str(me["csrf_token"])}


def _create_assignment(client: TestClient, headers: dict[str, str], **fields: object) -> dict:
    client_id = client.post(
        "/api/v1/ps/clients", json={"name": "Клиент"}, headers=headers,
    ).json()["id"]
    body = {"client_id": client_id, "title": "Оценка", **fields}
    resp = client.post("/api/v1/ps/assignments", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def test_risk_computed_at_creation(client: TestClient) -> None:
    _seed("Сервиз Риск", "risk@ps.bg")
    me = _login(client, "risk@ps.bg")
    headers = _headers(me)

    far = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    a = _create_assignment(client, headers, official_deadline_on=far)
    assert a["current_deadline_risk"] == "normal"
    assert a["current_stale"] is False

    overdue = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
    b = _create_assignment(client, headers, official_deadline_on=overdue)
    assert b["current_deadline_risk"] == "breached"

    c = _create_assignment(client, headers)  # no deadline at all
    assert c["current_deadline_risk"] == "none"


def test_change_deadline_requires_a_reason(client: TestClient) -> None:
    _seed("Сервиз Без Причина", "noreason@ps.bg")
    me = _login(client, "noreason@ps.bg")
    headers = _headers(me)

    a = _create_assignment(client, headers)
    new_date = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()

    resp = client.post(f"/api/v1/ps/assignments/{a['id']}/deadline",
                       json={"official_deadline_on": new_date, "reason": "   "}, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.ps.deadline_reason_required"


def test_change_deadline_recomputes_risk_and_writes_append_only_history(
    client: TestClient,
) -> None:
    company_id = _seed("Сервиз Промяна Срок", "changedeadline@ps.bg")
    me = _login(client, "changedeadline@ps.bg")
    headers = _headers(me)

    far = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    a = _create_assignment(client, headers, official_deadline_on=far)
    assert a["current_deadline_risk"] == "normal"

    soon = datetime.date.today().isoformat()  # due today
    resp = client.post(
        f"/api/v1/ps/assignments/{a['id']}/deadline",
        json={"official_deadline_on": soon, "reason": "клиентът поиска по-рано"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["official_deadline_on"] == soon
    assert updated["current_deadline_risk"] == "critical"

    resp = client.get(f"/api/v1/ps/assignments/{a['id']}/deadline-history", headers=headers)
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) == 1
    assert history[0]["new_value"] == soon
    assert history[0]["reason"] == "клиентът поиска по-рано"
    assert history[0]["old_value"] == far

    # Append-only at the DB level (PS-26 INV-11), same discipline as
    # ps_assignment_stage_history / timeline_events.
    from sqlalchemy.exc import ProgrammingError

    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from professional_services.assignments.models import PSDeadlineChange

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        bind_tenant_scope(db, company_id)
        row = db.query(PSDeadlineChange).order_by(PSDeadlineChange.changed_at.desc()).first()
        assert row is not None
        with pytest.raises(ProgrammingError, match="append-only"):
            row.reason = "tampered"
            db.commit()
        db.rollback()
        with pytest.raises(ProgrammingError, match="append-only"):
            db.delete(row)
            db.commit()
        db.rollback()


def test_delivery_stage_immediately_turns_off_risk(client: TestClient) -> None:
    _seed("Сервиз Предаване Риск", "deliveryrisk@ps.bg")
    me = _login(client, "deliveryrisk@ps.bg")
    headers = _headers(me)

    template = client.post(
        "/api/v1/ps/workflow-templates",
        json={"name": "Процес", "stages": [
            {"name": "Нов", "category": "work"},
            {"name": "Предаден", "category": "delivery"},
        ]},
        headers=headers,
    ).json()
    overdue = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
    a = _create_assignment(
        client, headers, workflow_template_id=template["id"], official_deadline_on=overdue,
    )
    assert a["current_deadline_risk"] == "breached"

    delivery_stage_id = client.get(
        f"/api/v1/ps/assignments/{a['id']}/stages", headers=headers,
    ).json()[-1]["id"]
    resp = client.post(f"/api/v1/ps/assignments/{a['id']}/stage",
                       json={"to_stage_id": delivery_stage_id}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["lifecycle_state"] == "delivered"
    assert resp.json()["current_deadline_risk"] == "none"


def test_evaluate_risk_is_idempotent(client: TestClient) -> None:
    _seed("Сервиз Идемпотентност", "idempotent@ps.bg")
    me = _login(client, "idempotent@ps.bg")
    headers = _headers(me)

    far = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    _create_assignment(client, headers, official_deadline_on=far)

    resp = client.post("/api/v1/ps/assignments/evaluate-risk", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["changed"] == 0  # already correct as of creation

    resp = client.post("/api/v1/ps/assignments/evaluate-risk", headers=headers)
    assert resp.json()["changed"] == 0


def test_evaluate_risk_gated_by_module_activation(client: TestClient) -> None:
    _seed("Сервиз Неактивен Риск", "inactive-risk@ps.bg", activate=False)
    _login(client, "inactive-risk@ps.bg")

    resp = client.post("/api/v1/ps/assignments/evaluate-risk")
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.ps.module_inactive"


def test_deadline_history_is_tenant_isolated(client: TestClient) -> None:
    _seed("Сервиз А Срок", "a-deadline@ps.bg")
    _seed("Сервиз Б Срок", "b-deadline@ps.bg")

    me_a = _login(client, "a-deadline@ps.bg")
    headers_a = _headers(me_a)
    a = _create_assignment(client, headers_a)

    client.post("/api/v1/auth/logout", headers=headers_a)
    me_b = _login(client, "b-deadline@ps.bg")
    headers_b = _headers(me_b)

    resp = client.get(f"/api/v1/ps/assignments/{a['id']}/deadline-history", headers=headers_b)
    assert resp.status_code == 404
