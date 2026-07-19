"""Customers API + the RLS net (P0-9 growth): first domain table under full isolation."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _seed_and_login(client: TestClient, company: str, email: str) -> str:
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, company, "Owner", email, "парола-123", "1234")
    me = client.post("/api/v1/auth/login",
                     json={"email": email, "password": "парола-123"}).json()
    return str(me["csrf_token"])


def test_create_search_and_duplicate_hint(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}

    r1 = client.post("/api/v1/customers", headers=h, json={
        "name": "Иван Петров", "phone": "+359 88 812 3456",
    })
    assert r1.status_code == 201
    assert r1.json()["duplicate_ids"] == []

    # Same phone in a different format → duplicate warning, creation still allowed.
    r2 = client.post("/api/v1/customers", headers=h, json={
        "name": "Ivan Petrov", "phone": "0888123456",
    })
    assert r2.status_code == 201
    assert r2.json()["duplicate_ids"] == [r1.json()["id"]]

    # Cyrillic and Latin queries both find both spellings; phone fragment works too.
    for q in ("Иван", "ivan", "0888123"):
        names = [c["name"] for c in client.get(f"/api/v1/customers?q={q}").json()]
        assert set(names) == {"Иван Петров", "Ivan Petrov"}, q


def test_archive_hides_from_default_list(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Мария", "phone": "0888000111",
    }).json()["id"]

    assert client.post(f"/api/v1/customers/{cid}/archive", headers=h).status_code == 200
    assert client.get("/api/v1/customers").json() == []
    listed = client.get("/api/v1/customers?include_archived=true").json()
    assert [c["id"] for c in listed] == [cid]


def test_anonymize_is_owner_only_and_irreversible(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Георги Личнев", "phone": "0899111222", "email": "g@x.bg",
        "notes": "личн данни",
    }).json()["id"]

    r = client.post(f"/api/v1/customers/{cid}/anonymize", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Изтрит клиент"
    assert body["phone"] == "" and body["email"] is None and body["notes"] == ""
    assert body["anonymized"] is True

    # Editing an anonymized customer is refused (history stays frozen).
    assert client.patch(f"/api/v1/customers/{cid}", headers=h,
                        json={"name": "Пак Георги"}).status_code == 409


def test_customers_are_tenant_isolated_via_api(client: TestClient) -> None:
    csrf_a = _seed_and_login(client, "Сервиз А", "a@a.bg")
    cid = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf_a}, json={
        "name": "Клиент на А", "phone": "0888999888",
    }).json()["id"]
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_a})

    _seed_and_login(client, "Сервиз Б", "b@b.bg")
    assert client.get("/api/v1/customers").json() == []
    assert client.get(f"/api/v1/customers/{cid}").status_code == 404


def test_rls_blocks_even_unscoped_queries(client: TestClient) -> None:
    """ADR-016 layer 3: a raw query that FORGETS scoped() still cannot cross tenants."""
    from sqlalchemy import select, text

    from business_os.shared_kernel.db import open_session
    from serviceflow.customers.models import Customer

    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Клиент на А", "phone": "0888999888",
    })

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    for db in open_session(url):
        # No GUC set → fail closed: zero rows even without any WHERE clause.
        assert db.scalars(select(Customer)).all() == []

        # GUC set to a random other company → still zero rows.
        db.execute(text(
            "SELECT set_config('app.company_id',"
            " '00000000-0000-0000-0000-000000000000', false)"
        ))
        assert db.scalars(select(Customer)).all() == []
