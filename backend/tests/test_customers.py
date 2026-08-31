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


def test_anonymize_is_blocked_for_non_owner(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    owner_h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=owner_h, json={
        "name": "Георги Личнев", "phone": "0899111222",
    }).json()["id"]
    client.post("/api/v1/users", headers=owner_h,
               json={"name": "Иво", "email": "ivo@a.bg", "password": "парола-за-иво-123"})
    client.post("/api/v1/auth/logout", headers=owner_h)

    worker_me = client.post("/api/v1/auth/login",
                            json={"email": "ivo@a.bg", "password": "парола-за-иво-123"}).json()
    worker_h = {"X-CSRF-Token": str(worker_me["csrf_token"])}
    r = client.post(f"/api/v1/customers/{cid}/anonymize", headers=worker_h)
    assert r.status_code == 403

    # Untouched — the customer must not have been anonymized by the attempt.
    assert client.get(f"/api/v1/customers/{cid}", headers=worker_h).json()["anonymized"] is False


def test_archive_alone_does_not_anonymize(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Георги Личнев", "phone": "0899111222",
    }).json()["id"]

    client.post(f"/api/v1/customers/{cid}/archive", headers=h)
    body = client.get(f"/api/v1/customers/{cid}", headers=h).json()
    assert body["archived"] is True
    assert body["anonymized"] is False
    assert body["name"] == "Георги Личнев"  # personal data still intact


# --- Wave 5 Issue 17: anonymization audit trail + Asset.sensitive_values ---

def test_anonymize_records_an_audit_event_without_leaking_personal_data(
    client: TestClient,
) -> None:
    from business_os.identity.models import AuditLog
    from business_os.shared_kernel.db import open_session

    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Георги Личнев", "phone": "0899111222", "email": "g@x.bg",
        "notes": "лична бележка",
    }).json()["id"]

    client.post(f"/api/v1/customers/{cid}/anonymize", headers=h)

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        rows = list(db.query(AuditLog).filter(AuditLog.action == "customer_anonymized"))
        assert len(rows) == 1
        detail = rows[0].detail
        assert detail == {"customer_id": cid}
        # No erased personal data anywhere in the audit payload.
        flattened = str(detail)
        for leaked in ("Георги Личнев", "0899111222", "g@x.bg", "лична бележка"):
            assert leaked not in flattened


def _asset_with_sensitive_value(client: TestClient, h: dict[str, str], cid: str) -> str:
    from business_os.shared_kernel.db import open_session
    from serviceflow.assets.models import Asset

    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone",
        "field_values": {"brand": "Apple", "model": "13", "imei": "356985061234567"},
    }).json()["id"]
    # No API writes sensitive_values yet (docs/08 §assets: "wired later") —
    # set it directly, simulating a stored encrypted passcode.
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        asset = db.get(Asset, aid)
        assert asset is not None
        asset.sensitive_values = b"encrypted-passcode-bytes"
        db.commit()
    return aid


def test_anonymize_clears_sensitive_values_for_currently_owned_assets(
    client: TestClient,
) -> None:
    from business_os.shared_kernel.db import open_session
    from serviceflow.assets.models import Asset

    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Георги", "phone": "0899111222",
    }).json()["id"]
    aid = _asset_with_sensitive_value(client, h, cid)

    client.post(f"/api/v1/customers/{cid}/anonymize", headers=h)

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        asset = db.get(Asset, aid)
        assert asset is not None
        assert asset.sensitive_values is None
        # Preserved: the asset row, its label, identifiers.
        assert asset.field_values["imei"] == "356985061234567"
        assert asset.archived_at is None


def test_anonymize_does_not_scrub_an_asset_now_owned_by_another_customer(
    client: TestClient,
) -> None:
    """Wave 3's AssetOwnership means Asset.customer_id is the CURRENT owner
    only — an asset customer A once owned but transferred away must not be
    damaged when A is later anonymized."""
    import uuid as uuid_mod

    from business_os.shared_kernel.db import open_session
    from serviceflow.assets.models import Asset

    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid_a = client.post("/api/v1/customers", headers=h, json={
        "name": "Собственик А", "phone": "0899111222",
    }).json()["id"]
    cid_b = client.post("/api/v1/customers", headers=h, json={
        "name": "Собственик Б", "phone": "0899333444",
    }).json()["id"]
    aid = _asset_with_sensitive_value(client, h, cid_a)

    r = client.post(f"/api/v1/assets/{aid}/transfer-owner", headers=h,
                    json={"customer_id": cid_b})
    assert r.status_code == 200, r.text

    client.post(f"/api/v1/customers/{cid_a}/anonymize", headers=h)

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        asset = db.get(Asset, aid)
        assert asset is not None
        assert asset.customer_id == uuid_mod.UUID(cid_b)
        # Still owned by B, whose passcode must survive A's anonymization.
        assert asset.sensitive_values == b"encrypted-passcode-bytes"


def test_anonymize_preserves_service_history(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Георги", "phone": "0899111222",
    }).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "phone", "field_values": {"brand": "Apple"},
    }).json()["id"]
    oid = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Счупен екран",
    }).json()["id"]

    client.post(f"/api/v1/customers/{cid}/anonymize", headers=h)

    order = client.get(f"/api/v1/orders/{oid}", headers=h)
    assert order.status_code == 200
    assert order.json()["complaint"] == "Счупен екран"
    assert order.json()["customer_id"] == cid


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
    assert body["vat_registered"] is None
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
    assert body["vat_registered"] is None  # unknown, never a silent False
    assert body["company_requisites"] == {
        "country": "BG", "address": "гр. София, бул. Витоша 1", "eik": "130489869",
        "vat_number": None,
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
    assert resp.json()["company_requisites"] == {
        "country": "BG", "address": "гр. Пловдив", "eik": "175074752", "vat_number": None,
    }


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
    assert resp.json()["company_requisites"] == {
        "country": "BG", "address": "гр. София", "eik": "130489869", "vat_number": None,
    }


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


# --- Wave 5 Issues 11/12: country + BG VAT prefill + delivery address ------

def test_new_company_customer_defaults_country_to_bg(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"address": "гр. София", "eik": "130489869"},
    })
    assert resp.status_code == 201
    assert resp.json()["company_requisites"]["country"] == "BG"


def test_legacy_company_customer_without_country_reads_as_bg(client: TestClient) -> None:
    """A company_requisites blob written before Wave 5 (no "country" key at
    all) must still read back as "BG" — the only country this product ever
    supported before this field existed — with no backfill migration."""
    from business_os.shared_kernel.db import open_session
    from serviceflow.customers.models import Customer

    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"address": "гр. София", "eik": "130489869"},
    }).json()["id"]

    # Simulate a pre-Wave-5 row: overwrite directly, stripping "country".
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        customer = db.get(Customer, cid)
        assert customer is not None
        customer.company_requisites = {"address": "гр. София", "eik": "130489869",
                                       "vat_number": None}
        db.commit()

    resp = client.get(f"/api/v1/customers/{cid}", headers=h)
    assert resp.json()["company_requisites"]["country"] == "BG"


def test_bg_eik_validation_still_applies_when_country_is_bg(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"country": "BG", "eik": "12345"},
    })
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_non_bg_company_skips_eik_structural_validation(client: TestClient) -> None:
    """A German company's identifier is accepted as typed — BG's 9/13-digit
    EIK shape rule was never true for it, so it is never applied."""
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Beispiel GmbH", "phone": "029001122", "is_company": True,
        "company_requisites": {"country": "DE", "eik": "HRB123456"},
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["company_requisites"] == {
        "country": "DE", "address": None, "eik": "HRB123456", "vat_number": None,
    }


def test_bg_vat_number_is_derived_from_valid_eik_when_registered(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "ДДС ЕООД", "phone": "029001133", "is_company": True,
        "vat_registered": True,
        "company_requisites": {"country": "BG", "eik": "130489869"},
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["company_requisites"]["vat_number"] == "BG130489869"


def test_vat_registration_is_never_inferred_from_eik_alone(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"country": "BG", "eik": "130489869"},
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["vat_registered"] is None
    assert body["company_requisites"]["vat_number"] is None


def test_bg_vat_number_derivation_never_overwrites_an_existing_value(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "ДДС ЕООД", "phone": "029001133", "is_company": True,
        "vat_registered": True,
        "company_requisites": {
            "country": "BG", "eik": "130489869", "vat_number": "BG175074752",
        },
    })
    assert resp.status_code == 201
    # Already on file (however it got there) — never silently replaced.
    assert resp.json()["company_requisites"]["vat_number"] == "BG175074752"


def test_non_bg_vat_registered_company_is_not_subject_to_bg_derivation(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Beispiel GmbH", "phone": "029001122", "is_company": True,
        "vat_registered": True,
        "company_requisites": {
            "country": "DE", "eik": "HRB123456", "vat_number": "DE123456789",
        },
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["company_requisites"]["vat_number"] == "DE123456789"


def test_default_delivery_address_create_and_update(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    resp = client.post("/api/v1/customers", headers=h, json={
        "name": "Иван Петров", "phone": "0888123456",
        "delivery_address": {"address": "ул. Тестова 5"},
    })
    assert resp.status_code == 201
    assert resp.json()["delivery_address"] == {"address": "ул. Тестова 5"}

    cid = resp.json()["id"]
    resp2 = client.patch(f"/api/v1/customers/{cid}", headers=h, json={
        "delivery_address": {"address": "ул. Нова 10"},
    })
    assert resp2.status_code == 200
    assert resp2.json()["delivery_address"] == {"address": "ул. Нова 10"}


def test_individual_customer_may_have_delivery_address_without_being_a_company(
    client: TestClient,
) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Иван Петров", "phone": "0888123456", "is_company": False,
        "delivery_address": {"address": "ул. Тестова 5"},
    })
    assert resp.status_code == 201
    assert resp.json()["is_company"] is False
    assert resp.json()["delivery_address"] == {"address": "ул. Тестова 5"}


def test_delivery_address_defaults_to_none(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Иван Петров", "phone": "0888123456",
    })
    assert resp.status_code == 201
    assert resp.json()["delivery_address"] is None


def test_registered_and_delivery_addresses_stay_distinct(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"country": "BG", "address": "гр. София (регистрация)"},
        "delivery_address": {"address": "гр. Пловдив (доставка)"},
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["company_requisites"]["address"] == "гр. София (регистрация)"
    assert body["delivery_address"]["address"] == "гр. Пловдив (доставка)"


# --- Customer VAT Identity prerequisite (docs/ACCOUNTANT_REVIEW.md §4 B1) ---
# Storage/API only — no Invoice Issue behavior. Customer.vat_registered is a
# tri-state column: NULL (unknown, never a silent False) / False (explicitly
# confirmed not VAT-registered) / True (explicitly confirmed, requires
# company_requisites.vat_number). See customers/service.py's
# _validate_vat_identity for the write-time rule this suite exercises.


def test_pre_existing_company_customer_migrates_to_vat_status_unknown(client: TestClient) -> None:
    """Simulates a row that existed before migration 0019 by writing
    directly at the DB layer (the only way to produce a row with no
    vat_registered value today, since every real write path now goes
    through this migration) — the API must read it back as UNKNOWN
    (None), never coerce a missing value into False."""
    import uuid as uuid_mod

    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.customers.models import Customer

    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Стара Фирма ЕООД", "phone": "029001199", "is_company": True,
        "company_requisites": {"address": "гр. Русе", "eik": "130489869"},
    }).json()["id"]

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    for db in open_session(url):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        customer = db.get(Customer, uuid_mod.UUID(cid))
        assert customer is not None
        assert customer.vat_registered is None  # migration 0019: no backfill, ever

    resp = client.get(f"/api/v1/customers/{cid}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["vat_registered"] is None
    # No existing data destroyed by the migration/read path.
    assert resp.json()["company_requisites"] == {
        "country": "BG", "address": "гр. Русе", "eik": "130489869", "vat_number": None,
    }


def test_create_company_with_unknown_vat_status(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"address": "гр. София", "eik": "130489869"},
    })
    assert resp.status_code == 201
    assert resp.json()["vat_registered"] is None


def test_create_company_explicitly_not_vat_registered(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "vat_registered": False,
        "company_requisites": {"address": "гр. София", "eik": "130489869"},
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["vat_registered"] is False
    assert body["company_requisites"]["vat_number"] is None


def test_create_vat_registered_company_with_vat_number(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "vat_registered": True,
        "company_requisites": {
            "address": "гр. София", "eik": "130489869", "vat_number": "BG130489869",
        },
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["vat_registered"] is True
    assert body["company_requisites"]["vat_number"] == "BG130489869"


def test_vat_registered_true_without_vat_number_is_rejected(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "vat_registered": True,
        "company_requisites": {"address": "гр. София", "eik": "130489869"},
    })
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.customers.vat_number_required"


def test_vat_registered_true_without_vat_number_is_rejected_on_update(client: TestClient) -> None:
    """The merged-effective-state rule: a PATCH that sets vat_registered=True
    without also supplying company_requisites (leaving vat_number at its
    already-None stored value) must be rejected too — not just the
    single-request create case."""
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"address": "гр. София", "eik": "130489869"},
    }).json()["id"]

    resp = client.patch(f"/api/v1/customers/{cid}", headers=h, json={"vat_registered": True})
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.customers.vat_number_required"


@pytest.mark.parametrize("bad_vat", ["BG12345", "130489869", "US130489869", "bg-130489869"])
def test_malformed_vat_number_is_rejected(client: TestClient, bad_vat: str) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "vat_registered": True,
        "company_requisites": {
            "address": "гр. София", "eik": "130489869", "vat_number": bad_vat,
        },
    })
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_vat_number_normalizes_case_and_whitespace(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    resp = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf}, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "vat_registered": True,
        "company_requisites": {
            "address": "гр. София", "eik": "130489869", "vat_number": "  bg 130489869  ",
        },
    })
    assert resp.status_code == 201
    assert resp.json()["company_requisites"]["vat_number"] == "BG130489869"


def test_update_unknown_to_not_vat_registered(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"address": "гр. София", "eik": "130489869"},
    }).json()["id"]

    resp = client.patch(f"/api/v1/customers/{cid}", headers=h, json={"vat_registered": False})
    assert resp.status_code == 200
    assert resp.json()["vat_registered"] is False


def test_update_unknown_to_vat_registered_with_number(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"address": "гр. София", "eik": "130489869"},
    }).json()["id"]

    resp = client.patch(f"/api/v1/customers/{cid}", headers=h, json={
        "vat_registered": True,
        "company_requisites": {
            "address": "гр. София", "eik": "130489869", "vat_number": "BG130489869",
        },
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["vat_registered"] is True
    assert body["company_requisites"]["vat_number"] == "BG130489869"


def test_update_vat_number_while_already_registered(client: TestClient) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "vat_registered": True,
        "company_requisites": {
            "address": "гр. София", "eik": "130489869", "vat_number": "BG130489869",
        },
    }).json()["id"]

    resp = client.patch(f"/api/v1/customers/{cid}", headers=h, json={
        "company_requisites": {
            "address": "гр. София", "eik": "130489869", "vat_number": "BG175074752",
        },
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["vat_registered"] is True  # untouched by this patch, stays True
    assert body["company_requisites"]["vat_number"] == "BG175074752"


def test_vat_identity_fields_are_tenant_isolated(client: TestClient) -> None:
    csrf_a = _seed_and_login(client, "Сервиз А", "a@a.bg")
    cid = client.post("/api/v1/customers", headers={"X-CSRF-Token": csrf_a}, json={
        "name": "Фирма А ЕООД", "phone": "029001122", "is_company": True,
        "vat_registered": True,
        "company_requisites": {
            "address": "Адрес А", "eik": "130489869", "vat_number": "BG130489869",
        },
    }).json()["id"]
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_a})

    _seed_and_login(client, "Сервиз Б", "b@b.bg")
    assert client.get("/api/v1/customers").json() == []
    assert client.get(f"/api/v1/customers/{cid}").status_code == 404


@pytest.mark.parametrize("vat_registered", [None, False, True])
def test_read_contract_round_trips_every_vat_status(
    client: TestClient, vat_registered: bool | None,
) -> None:
    csrf = _seed_and_login(client, "Сервиз А", "a@a.bg")
    h = {"X-CSRF-Token": csrf}
    payload: dict[str, object] = {
        "name": "Пример ЕООД", "phone": "029001122", "is_company": True,
        "company_requisites": {"address": "гр. София", "eik": "130489869"},
    }
    if vat_registered is not None:
        payload["vat_registered"] = vat_registered
        if vat_registered:
            payload["company_requisites"] = {
                "address": "гр. София", "eik": "130489869", "vat_number": "BG130489869",
            }
    created = client.post("/api/v1/customers", headers=h, json=payload).json()

    fetched = client.get(f"/api/v1/customers/{created['id']}", headers=h).json()
    assert fetched["vat_registered"] == vat_registered
    assert fetched["company_requisites"] == created["company_requisites"]
