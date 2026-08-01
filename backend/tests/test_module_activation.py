"""Module activation (BOS-06): active_modules inside companies.settings JSONB,
no dedicated table. Centralized behind business_os.identity.service/.contracts —
this test is also the isolation proof: one company's activation must never
leak into another's."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _seed(company: str, email: str, password: str = "парола-123") -> str:
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    company_id = ""
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        row = seed_company(db, company, "Мария", email, password)
        company_id = str(row.id)
    return company_id


def _login(client: TestClient, email: str, password: str = "парола-123") -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def test_inactive_by_default(client: TestClient) -> None:
    """`professional-services` (unlike `"repairflow"`, which `seed_company`
    grants unconditionally since the 01.08.2026 PO decision) is inactive
    until something explicitly activates it."""
    _seed("Сервиз А", "a@a.bg")
    me = _login(client, "a@a.bg")
    assert me["active_modules"] == ["repairflow"]


def test_activate_module_is_idempotent_and_scoped(client: TestClient) -> None:
    import uuid

    from business_os.identity.service import (
        activate_module,
        is_module_active,
    )
    from business_os.shared_kernel.db import open_session

    company_id_a = uuid.UUID(_seed("Сервиз Б", "b@b.bg"))
    company_id_c = uuid.UUID(_seed("Сервиз В", "c@c.bg"))

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        activate_module(db, company_id_a, "professional-services")
        activate_module(db, company_id_a, "professional-services")  # idempotent, no crash
        assert is_module_active(db, company_id_a, "professional-services") is True
        # Never leaks to the other company:
        assert is_module_active(db, company_id_c, "professional-services") is False
        assert is_module_active(db, company_id_a, "construction-supervision") is False


def test_me_reflects_activation(client: TestClient) -> None:
    import uuid

    from business_os.identity.service import activate_module
    from business_os.shared_kernel.db import open_session

    company_id = uuid.UUID(_seed("Сервиз Г", "d@d.bg"))
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        activate_module(db, company_id, "professional-services")

    me = _login(client, "d@d.bg")
    assert set(me["active_modules"]) == {"repairflow", "professional-services"}
