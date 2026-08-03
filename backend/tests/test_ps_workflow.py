"""Professional Services two-axis workflow model (ADR-PS-005, migration 0010):
configurable workflow templates, code-owned stage categories, copy-on-create,
the single transition chokepoint, and its append-only history."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)

VALUATION_STAGES = [
    {"name": "Ново запитване", "category": "work"},
    {"name": "Чакане на документи", "category": "waiting_documents"},
    {"name": "Оглед", "category": "work"},
    {"name": "Вътрешна проверка", "category": "review"},
    {"name": "Предаване", "category": "delivery"},
]


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


def _create_template(client: TestClient, headers: dict[str, str], stages: list) -> dict:
    resp = client.post(
        "/api/v1/ps/workflow-templates",
        json={"name": "Оценка на имот", "stages": stages},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def test_create_template_with_stages_and_list(client: TestClient) -> None:
    _seed("Сервиз Шаблон", "template@ps.bg")
    me = _login(client, "template@ps.bg")
    headers = _headers(me)

    template = _create_template(client, headers, VALUATION_STAGES)
    assert len(template["stages"]) == 5
    assert [s["name"] for s in template["stages"]] == [s["name"] for s in VALUATION_STAGES]
    assert [s["category"] for s in template["stages"]] == [s["category"] for s in VALUATION_STAGES]
    assert template["stages"][0]["sort"] == 0
    assert template["stages"][-1]["sort"] == 4

    resp = client.get("/api/v1/ps/workflow-templates", headers=headers)
    assert resp.status_code == 200
    assert any(t["id"] == template["id"] for t in resp.json())


def test_create_template_rejects_unknown_category(client: TestClient) -> None:
    _seed("Сервиз Невалидна Категория", "badcat@ps.bg")
    me = _login(client, "badcat@ps.bg")
    headers = _headers(me)

    resp = client.post(
        "/api/v1/ps/workflow-templates",
        json={"name": "Лош шаблон", "stages": [{"name": "X", "category": "not_a_real_category"}]},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.ps.invalid_stage_category"


def test_create_template_rejects_empty_stage_list(client: TestClient) -> None:
    _seed("Сервиз Без Етапи", "nostage@ps.bg")
    me = _login(client, "nostage@ps.bg")
    headers = _headers(me)

    resp = client.post(
        "/api/v1/ps/workflow-templates", json={"name": "Празен", "stages": []}, headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.ps.template_needs_stages"


def test_copy_on_create_proof(client: TestClient) -> None:
    """The heart of ADR-PS-005: an assignment's stages are copied at creation;
    editing the template afterwards never touches the assignment's own copy."""
    _seed("Сервиз Копие", "copy@ps.bg")
    me = _login(client, "copy@ps.bg")
    headers = _headers(me)

    template = _create_template(client, headers, VALUATION_STAGES)

    client_id = client.post(
        "/api/v1/ps/clients", json={"name": "Инвест ЕООД", "kind": "company"}, headers=headers,
    ).json()["id"]
    resp = client.post(
        "/api/v1/ps/assignments",
        json={"client_id": client_id, "title": "Оценка на апартамент",
              "workflow_template_id": template["id"]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assignment = resp.json()
    assert assignment["current_stage"]["name"] == "Ново запитване"
    assert assignment["current_stage"]["category"] == "work"

    resp = client.get(f"/api/v1/ps/assignments/{assignment['id']}/stages", headers=headers)
    assert resp.status_code == 200
    own_stages = resp.json()
    assert [s["name"] for s in own_stages] == [s["name"] for s in VALUATION_STAGES]
    # Own copy has its own ids, distinct from the template's stage ids.
    template_stage_ids = {s["id"] for s in template["stages"]}
    own_stage_ids = {s["id"] for s in own_stages}
    assert template_stage_ids.isdisjoint(own_stage_ids)

    # Editing the template's content afterwards (PUT .../workflow-templates/{id},
    # see test_update_template_never_touches_already_copied_assignment_stages
    # below) never touches this assignment's own copy - the isolation proof
    # that matters here is structural: the assignment's stages are a separate
    # row set with separate ids, already asserted above. A second assignment
    # from the same template gets its own independent copy too:
    resp2 = client.post(
        "/api/v1/ps/assignments",
        json={"client_id": client_id, "title": "Втора оценка",
              "workflow_template_id": template["id"]},
        headers=headers,
    )
    assert resp2.status_code == 200
    second_stage_ids = {
        s["id"] for s in client.get(
            f"/api/v1/ps/assignments/{resp2.json()['id']}/stages", headers=headers,
        ).json()
    }
    assert second_stage_ids.isdisjoint(own_stage_ids)


def test_assignment_without_template_has_no_current_stage(client: TestClient) -> None:
    _seed("Сервиз Без Шаблон", "notemplate@ps.bg")
    me = _login(client, "notemplate@ps.bg")
    headers = _headers(me)

    client_id = client.post(
        "/api/v1/ps/clients", json={"name": "Клиент"}, headers=headers,
    ).json()["id"]
    resp = client.post(
        "/api/v1/ps/assignments", json={"client_id": client_id, "title": "Консултация"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["current_stage"] is None


def test_stage_transition_chokepoint_and_history(client: TestClient) -> None:
    company_id = _seed("Сервиз Преход", "transition@ps.bg")
    me = _login(client, "transition@ps.bg")
    headers = _headers(me)

    template = _create_template(client, headers, VALUATION_STAGES)
    client_id = client.post(
        "/api/v1/ps/clients", json={"name": "Клиент Х"}, headers=headers,
    ).json()["id"]
    assignment = client.post(
        "/api/v1/ps/assignments",
        json={"client_id": client_id, "title": "Оценка", "workflow_template_id": template["id"]},
        headers=headers,
    ).json()
    own_stages = client.get(
        f"/api/v1/ps/assignments/{assignment['id']}/stages", headers=headers,
    ).json()
    second_stage = own_stages[1]

    resp = client.post(
        f"/api/v1/ps/assignments/{assignment['id']}/stage",
        json={"to_stage_id": second_stage["id"]}, headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["current_stage"]["id"] == second_stage["id"]

    # Append-only history row exists and cannot be rewritten (PS-26 INV-10),
    # same discipline test_timeline.py proves for timeline_events.
    from sqlalchemy.exc import ProgrammingError

    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from professional_services.assignments.models import PSAssignmentStageHistory

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        bind_tenant_scope(db, company_id)
        row = db.query(PSAssignmentStageHistory).order_by(
            PSAssignmentStageHistory.changed_at.desc()
        ).first()
        assert row is not None
        assert str(row.to_stage_id) == second_stage["id"]
        assert row.from_stage_id is not None

        with pytest.raises(ProgrammingError, match="append-only"):
            row.to_stage_id = row.from_stage_id
            db.commit()
        db.rollback()
        with pytest.raises(ProgrammingError, match="append-only"):
            db.delete(row)
            db.commit()
        db.rollback()


def test_stage_transition_rejects_stage_from_another_assignment(client: TestClient) -> None:
    _seed("Сервиз Чужд Етап", "foreignstage@ps.bg")
    me = _login(client, "foreignstage@ps.bg")
    headers = _headers(me)

    template = _create_template(client, headers, VALUATION_STAGES)
    client_id = client.post(
        "/api/v1/ps/clients", json={"name": "Клиент"}, headers=headers,
    ).json()["id"]
    a1 = client.post(
        "/api/v1/ps/assignments",
        json={"client_id": client_id, "title": "Първа", "workflow_template_id": template["id"]},
        headers=headers,
    ).json()
    a2 = client.post(
        "/api/v1/ps/assignments",
        json={"client_id": client_id, "title": "Втора", "workflow_template_id": template["id"]},
        headers=headers,
    ).json()
    a2_stage_id = client.get(
        f"/api/v1/ps/assignments/{a2['id']}/stages", headers=headers,
    ).json()[1]["id"]

    resp = client.post(
        f"/api/v1/ps/assignments/{a1['id']}/stage",
        json={"to_stage_id": a2_stage_id}, headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.ps.invalid_stage"


def test_stage_transition_rejects_no_op(client: TestClient) -> None:
    _seed("Сервиз Без Промяна", "noop@ps.bg")
    me = _login(client, "noop@ps.bg")
    headers = _headers(me)

    template = _create_template(client, headers, VALUATION_STAGES)
    client_id = client.post(
        "/api/v1/ps/clients", json={"name": "Клиент"}, headers=headers,
    ).json()["id"]
    assignment = client.post(
        "/api/v1/ps/assignments",
        json={"client_id": client_id, "title": "Оценка", "workflow_template_id": template["id"]},
        headers=headers,
    ).json()

    resp = client.post(
        f"/api/v1/ps/assignments/{assignment['id']}/stage",
        json={"to_stage_id": assignment["current_stage"]["id"]}, headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.ps.stage_unchanged"


def test_delivery_category_stage_sets_lifecycle_delivered(client: TestClient) -> None:
    _seed("Сервиз Предаване", "delivery@ps.bg")
    me = _login(client, "delivery@ps.bg")
    headers = _headers(me)

    template = _create_template(client, headers, VALUATION_STAGES)
    client_id = client.post(
        "/api/v1/ps/clients", json={"name": "Клиент"}, headers=headers,
    ).json()["id"]
    assignment = client.post(
        "/api/v1/ps/assignments",
        json={"client_id": client_id, "title": "Оценка", "workflow_template_id": template["id"]},
        headers=headers,
    ).json()
    assert assignment["lifecycle_state"] == "active"
    delivery_stage_id = client.get(
        f"/api/v1/ps/assignments/{assignment['id']}/stages", headers=headers,
    ).json()[-1]["id"]

    resp = client.post(
        f"/api/v1/ps/assignments/{assignment['id']}/stage",
        json={"to_stage_id": delivery_stage_id}, headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["lifecycle_state"] == "delivered"


def test_cross_tenant_template_is_invisible(client: TestClient) -> None:
    _seed("Сервиз А Шаблон", "a-template@ps.bg")
    _seed("Сервиз Б Шаблон", "b-template@ps.bg")

    me_a = _login(client, "a-template@ps.bg")
    headers_a = _headers(me_a)
    template_a = _create_template(client, headers_a, VALUATION_STAGES)

    client.post("/api/v1/auth/logout", headers=headers_a)
    me_b = _login(client, "b-template@ps.bg")
    headers_b = _headers(me_b)

    resp = client.get(f"/api/v1/ps/workflow-templates/{template_a['id']}", headers=headers_b)
    assert resp.status_code == 404

    client_id_b = client.post(
        "/api/v1/ps/clients", json={"name": "Клиент Б"}, headers=headers_b,
    ).json()["id"]
    resp = client.post(
        "/api/v1/ps/assignments",
        json={"client_id": client_id_b, "title": "Крадена оценка",
              "workflow_template_id": template_a["id"]},
        headers=headers_b,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.ps.template_needs_stages"


def test_catalog_routes_404_when_module_inactive(client: TestClient) -> None:
    _seed("Сервиз Неактивен Каталог", "inactive-catalog@ps.bg", activate=False)
    _login(client, "inactive-catalog@ps.bg")

    resp = client.get("/api/v1/ps/workflow-templates")
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.ps.module_inactive"


NEW_STAGES = [
    {"name": "Първи контакт", "category": "work"},
    {"name": "Одобрение", "category": "review"},
]


def test_update_template_replaces_name_and_stages(client: TestClient) -> None:
    _seed("Сервиз Редакция", "edit@ps.bg")
    me = _login(client, "edit@ps.bg")
    headers = _headers(me)
    template = _create_template(client, headers, VALUATION_STAGES)

    resp = client.put(
        f"/api/v1/ps/workflow-templates/{template['id']}",
        json={"name": "Преработена оценка", "stages": NEW_STAGES},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == template["id"]
    assert body["name"] == "Преработена оценка"
    assert [s["name"] for s in body["stages"]] == [s["name"] for s in NEW_STAGES]
    assert [s["category"] for s in body["stages"]] == [s["category"] for s in NEW_STAGES]
    # New stage rows replace the old ones entirely (not appended alongside).
    assert {s["id"] for s in body["stages"]}.isdisjoint({s["id"] for s in template["stages"]})

    refetched = client.get(
        f"/api/v1/ps/workflow-templates/{template['id']}", headers=headers,
    ).json()
    assert refetched["name"] == "Преработена оценка"
    assert len(refetched["stages"]) == 2


def test_update_template_rejects_empty_stage_list(client: TestClient) -> None:
    _seed("Сервиз Редакция Празно", "edit-empty@ps.bg")
    me = _login(client, "edit-empty@ps.bg")
    headers = _headers(me)
    template = _create_template(client, headers, VALUATION_STAGES)

    resp = client.put(
        f"/api/v1/ps/workflow-templates/{template['id']}",
        json={"name": template["name"], "stages": []},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.ps.template_needs_stages"


def test_update_template_rejects_unknown_category(client: TestClient) -> None:
    _seed("Сервиз Редакция Категория", "edit-cat@ps.bg")
    me = _login(client, "edit-cat@ps.bg")
    headers = _headers(me)
    template = _create_template(client, headers, VALUATION_STAGES)

    resp = client.put(
        f"/api/v1/ps/workflow-templates/{template['id']}",
        json={"name": template["name"], "stages": [{"name": "X", "category": "not_real"}]},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.ps.invalid_stage_category"


def test_update_template_404s_for_nonexistent_template(client: TestClient) -> None:
    _seed("Сервиз Редакция Липсва", "edit-missing@ps.bg")
    me = _login(client, "edit-missing@ps.bg")
    headers = _headers(me)

    resp = client.put(
        f"/api/v1/ps/workflow-templates/{uuid.uuid4()}",
        json={"name": "X", "stages": NEW_STAGES},
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.ps.template_not_found"


def test_update_template_404s_cross_tenant(client: TestClient) -> None:
    _seed("Сервиз А Редакция", "a-edit@ps.bg")
    _seed("Сервиз Б Редакция", "b-edit@ps.bg")

    me_a = _login(client, "a-edit@ps.bg")
    headers_a = _headers(me_a)
    template_a = _create_template(client, headers_a, VALUATION_STAGES)

    client.post("/api/v1/auth/logout", headers=headers_a)
    me_b = _login(client, "b-edit@ps.bg")
    headers_b = _headers(me_b)

    resp = client.put(
        f"/api/v1/ps/workflow-templates/{template_a['id']}",
        json={"name": "Отвлечен", "stages": NEW_STAGES},
        headers=headers_b,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["message_key"] == "errors.ps.template_not_found"


def test_update_template_never_touches_already_copied_assignment_stages(
    client: TestClient,
) -> None:
    """The invariant this whole slice hinges on (ADR-PS-005 copy-on-create):
    editing a template's stages after an assignment has already copied them
    must leave that assignment's own stages completely untouched."""
    _seed("Сервиз Редакция Копие", "edit-copy@ps.bg")
    me = _login(client, "edit-copy@ps.bg")
    headers = _headers(me)
    template = _create_template(client, headers, VALUATION_STAGES)

    client_id = client.post(
        "/api/v1/ps/clients", json={"name": "Клиент"}, headers=headers,
    ).json()["id"]
    assignment = client.post(
        "/api/v1/ps/assignments",
        json={"client_id": client_id, "title": "Оценка", "workflow_template_id": template["id"]},
        headers=headers,
    ).json()
    before_stages = client.get(
        f"/api/v1/ps/assignments/{assignment['id']}/stages", headers=headers,
    ).json()

    resp = client.put(
        f"/api/v1/ps/workflow-templates/{template['id']}",
        json={"name": "Съвсем друго", "stages": NEW_STAGES},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    after_stages = client.get(
        f"/api/v1/ps/assignments/{assignment['id']}/stages", headers=headers,
    ).json()
    assert after_stages == before_stages

    # A brand-new assignment from the (now-edited) template gets the new stages.
    resp2 = client.post(
        "/api/v1/ps/assignments",
        json={"client_id": client_id, "title": "Втора оценка",
              "workflow_template_id": template["id"]},
        headers=headers,
    )
    assert resp2.status_code == 200, resp2.text
    new_own_stages = client.get(
        f"/api/v1/ps/assignments/{resp2.json()['id']}/stages", headers=headers,
    ).json()
    assert [s["name"] for s in new_own_stages] == [s["name"] for s in NEW_STAGES]
