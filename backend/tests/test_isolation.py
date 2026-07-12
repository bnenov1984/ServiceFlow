"""P0-9 seed: tenant isolation at the identity bootstrap (ADR-016).

Grows with every domain table; cross-company invisibility is a release blocker.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def test_pin_switch_cannot_cross_companies(client: TestClient) -> None:
    from serviceflow.identity.models import User
    from serviceflow.identity.service import seed_company
    from serviceflow.shared_kernel.db import open_session

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    for db in open_session(url):
        seed_company(db, "Сервиз А", "Мария", "maria@a.bg", "парола-123", "1234")
        seed_company(db, "Сервиз Б", "Борис", "boris@b.bg", "парола-999", "9999")
        boris = db.scalar(select(User).where(User.email == "boris@b.bg"))
        assert boris is not None
        boris_id = str(boris.id)

    me = client.post("/api/v1/auth/login",
                     json={"email": "maria@a.bg", "password": "парола-123"}).json()

    # Maria (company A) tries to PIN-switch to Boris (company B) with his real PIN:
    # must fail identically to a wrong PIN — no cross-tenant information leak.
    resp = client.post("/api/v1/auth/pin-switch",
                       headers={"X-CSRF-Token": str(me["csrf_token"])},
                       json={"user_id": boris_id, "pin": "9999"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["message_key"] == "errors.auth.invalid_pin"


def test_scoped_chokepoint_filters_by_company(client: TestClient) -> None:
    from serviceflow.identity.models import User
    from serviceflow.identity.service import seed_company
    from serviceflow.shared_kernel.db import TenantContext, open_session, scoped

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    for db in open_session(url):
        a = seed_company(db, "Сервиз А", "Мария", "maria@a.bg", "парола-123")
        seed_company(db, "Сервиз Б", "Борис", "boris@b.bg", "парола-999")
        maria = db.scalar(select(User).where(User.email == "maria@a.bg"))
        assert maria is not None
        ctx = TenantContext(company_id=a.id, user_id=maria.id, is_owner=True)

        emails = db.scalars(scoped(select(User), User, ctx)).all()
        assert [u.email for u in emails] == ["maria@a.bg"]
