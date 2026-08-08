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


def test_individual_customer_creation_is_unchanged(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Иван Петров", "phone": "0888123456",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_company"] is False
    assert body["company_requisites"] is None


def test_company_customer_can_be_created_with_approved_requisites(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"address": "гр. София, бул. Витоша 1", "eik": "130489869"},
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_company"] is True
    assert body["company_requisites"] == {
        "address": "гр. София, бул. Витоша 1", "eik": "130489869",
    }


def test_company_customer_requisites_can_be_updated(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"address": "гр. София", "eik": "130489869"},
    }).json()["id"]

    resp = client.patch(f"/api/v1/customers/{cid}", headers=h, json={
        "company_requisites": {"address": "гр. Пловдив", "eik": "175074752"},
    })
    assert resp.status_code == 200
    assert resp.json()["company_requisites"] == {"address": "гр. Пловдив", "eik": "175074752"}


def test_unknown_company_requisites_key_is_rejected(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    # "iban" is not on the approved buyer-company list (docs/ACCOUNTANT_REVIEW.md
    # §4 B1) — extra="forbid" must reject it, not silently store it.
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"iban": "BG80BNBG96611020345678"},
    })
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


@pytest.mark.parametrize("bad_eik", ["12345", "12345678901234", "not-digits"])
def test_malformed_company_eik_is_rejected(client: TestClient, bad_eik: str) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"eik": bad_eik},
    })
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_company_customers_are_tenant_isolated(client: TestClient) -> None:
    csrf_a = _seed_and_login(client, "Сервиз А", "a@a.bg")
    client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf_a}, json={
        "name": "Фирма А ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"address": "Адрес А", "eik": "130489869"},
    })
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_a})

    _seed_and_login(client, "Сервиз Б", "b@b.bg")
    assert client.get("/api/v1/customers").json() == []


def test_existing_customer_records_remain_readable(client: TestClient) -> None:
    """A customer created before this slice (no is_company/company_requisites
    in the payload) must still read back cleanly under the tightened schema."""
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Стар клиент", "phone": "0888000111",
    }).json()["id"]

    resp = client.get(f"/api/v1/customers/{cid}")
    assert resp.status_code == 200
    assert resp.json()["is_company"] is False
    assert resp.json()["company_requisites"] is None


def test_is_company_round_trips_without_touching_requisites(client: TestClient) -> None:
    """Toggling is_company alone must not destructively clear
    company_requisites — preservation over destructive mutation unless a
    stronger existing contract says otherwise (none does here)."""
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"address": "гр. София", "eik": "130489869"},
    }).json()["id"]

    resp = client.patch(f"/api/v1/customers/{cid}", headers=h, json={"is_company": False})
    assert resp.status_code == 200
    assert resp.json()["is_company"] is False
    assert resp.json()["company_requisites"] == {"address": "гр. София", "eik": "130489869"}


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
