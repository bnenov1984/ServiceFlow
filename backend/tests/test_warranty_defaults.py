"""RepairFlow warranty defaults (Wave 4 Issue 38): Owner-only read/update of
`companies.settings.repairflow.warranty_defaults` — same JSONB-bag/allow-list
discipline as company requisites (test_company_requisites.py), no new table,
no migration. `labor_days`/`parts_days`: NULL/missing = no default
configured, 0 = explicitly "Без гаранция", positive = days, negative
rejected. Also exposed (read-only) on /auth/me for any authenticated user —
CompletionDialog/PartLinesSection prefill needs it without an owner-only gate.

Audit correction (issue 04, 2026-09-25) added four free-text fields
(standard_term/conditions/text/additional_conditions) to the same shape —
every response below now carries all six keys, not just the original two.
"""

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)

OWNER_EMAIL = "maria@a.bg"
OWNER_PASSWORD = "парола-123"

# The four text fields added by issue 04 — every response carries these
# alongside labor_days/parts_days; tests that don't touch them assert None.
_BLANK_TERMS = {
    "standard_term": None, "conditions": None, "text": None, "additional_conditions": None,
}


def _db() -> Iterator[object]:
    from business_os.shared_kernel.db import open_session

    return open_session(os.environ["SERVICEFLOW_DATABASE_URL"])


def _seed_owner(company: str = "Сервиз А", email: str = OWNER_EMAIL) -> uuid.UUID:
    from business_os.identity.service import seed_company

    for db in _db():
        seeded = seed_company(db, company, "Мария", email, OWNER_PASSWORD, "1234")
        return seeded.id
    raise AssertionError("unreachable")


def _login(client: TestClient, email: str = OWNER_EMAIL,
          password: str = OWNER_PASSWORD) -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def test_defaults_read_as_null_when_unconfigured(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)

    resp = client.get("/api/v1/company/warranty-defaults",
                      headers={"X-CSRF-Token": str(me["csrf_token"])})
    assert resp.status_code == 200
    assert resp.json() == {"labor_days": None, "parts_days": None, **_BLANK_TERMS}


def test_owner_can_set_positive_defaults(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    resp = client.patch("/api/v1/company/warranty-defaults", headers=headers,
                        json={"labor_days": 90, "parts_days": 30})
    assert resp.status_code == 200
    assert resp.json() == {"labor_days": 90, "parts_days": 30, **_BLANK_TERMS}

    resp2 = client.get("/api/v1/company/warranty-defaults", headers=headers)
    assert resp2.json() == {"labor_days": 90, "parts_days": 30, **_BLANK_TERMS}


def test_zero_means_explicitly_no_warranty(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    resp = client.patch("/api/v1/company/warranty-defaults", headers=headers,
                        json={"labor_days": 0})
    assert resp.status_code == 200
    assert resp.json()["labor_days"] == 0


def test_explicit_null_clears_a_previously_set_default(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    client.patch("/api/v1/company/warranty-defaults", headers=headers, json={"labor_days": 90})
    resp = client.patch("/api/v1/company/warranty-defaults", headers=headers,
                        json={"labor_days": None})
    assert resp.status_code == 200
    assert resp.json()["labor_days"] is None


def test_partial_update_leaves_the_other_field_untouched(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    client.patch("/api/v1/company/warranty-defaults", headers=headers,
                json={"labor_days": 90, "parts_days": 30})
    resp = client.patch("/api/v1/company/warranty-defaults", headers=headers,
                        json={"labor_days": 60})
    assert resp.status_code == 200
    assert resp.json() == {"labor_days": 60, "parts_days": 30, **_BLANK_TERMS}


def test_owner_can_set_warranty_terms_text_fields(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    resp = client.patch("/api/v1/company/warranty-defaults", headers=headers, json={
        "standard_term": "12 месеца",
        "conditions": "Гаранцията покрива производствени дефекти.",
        "text": "Пълен текст на гаранционните условия на сервиза.",
        "additional_conditions": "Не се покриват щети от вода.",
    })
    assert resp.status_code == 200
    assert resp.json() == {
        "labor_days": None, "parts_days": None,
        "standard_term": "12 месеца",
        "conditions": "Гаранцията покрива производствени дефекти.",
        "text": "Пълен текст на гаранционните условия на сервиза.",
        "additional_conditions": "Не се покриват щети от вода.",
    }

    resp2 = client.get("/api/v1/company/warranty-defaults", headers=headers)
    assert resp2.json() == resp.json()


def test_setting_one_text_field_leaves_others_untouched(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    headers = {"X-CSRF-Token": str(me["csrf_token"])}

    client.patch("/api/v1/company/warranty-defaults", headers=headers,
                json={"standard_term": "12 месеца", "conditions": "Условие А"})
    resp = client.patch("/api/v1/company/warranty-defaults", headers=headers,
                        json={"conditions": "Условие Б"})
    assert resp.status_code == 200
    assert resp.json()["standard_term"] == "12 месеца"
    assert resp.json()["conditions"] == "Условие Б"


@pytest.mark.parametrize(("field", "limit"), [
    ("standard_term", 200), ("conditions", 2000), ("text", 4000), ("additional_conditions", 2000),
])
def test_warranty_terms_text_field_over_max_length_is_rejected(
    client: TestClient, field: str, limit: int,
) -> None:
    _seed_owner()
    me = _login(client)
    resp = client.patch("/api/v1/company/warranty-defaults",
                        headers={"X-CSRF-Token": str(me["csrf_token"])},
                        json={field: "x" * (limit + 1)})
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


@pytest.mark.parametrize("field", ["labor_days", "parts_days"])
def test_negative_value_is_rejected(client: TestClient, field: str) -> None:
    _seed_owner()
    me = _login(client)
    resp = client.patch("/api/v1/company/warranty-defaults",
                        headers={"X-CSRF-Token": str(me["csrf_token"])},
                        json={field: -1})
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_unlisted_key_is_rejected(client: TestClient) -> None:
    _seed_owner()
    me = _login(client)
    resp = client.patch("/api/v1/company/warranty-defaults",
                        headers={"X-CSRF-Token": str(me["csrf_token"])},
                        json={"tax_days": 10})
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_worker_cannot_read_or_update_warranty_defaults(client: TestClient) -> None:
    _seed_owner()
    owner_me = _login(client)
    client.post("/api/v1/users", headers={"X-CSRF-Token": str(owner_me["csrf_token"])},
               json={"name": "Иво", "email": "ivo@a.bg", "password": "парола-за-иво-123"})
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": str(owner_me["csrf_token"])})

    worker_me = _login(client, email="ivo@a.bg", password="парола-за-иво-123")
    headers = {"X-CSRF-Token": str(worker_me["csrf_token"])}

    assert client.get("/api/v1/company/warranty-defaults", headers=headers).status_code == 403
    resp = client.patch("/api/v1/company/warranty-defaults", headers=headers,
                        json={"labor_days": 30})
    assert resp.status_code == 403


def test_warranty_defaults_are_tenant_isolated(client: TestClient) -> None:
    _seed_owner("Сервиз А", OWNER_EMAIL)
    _seed_owner("Сервиз Б", "petar@b.bg")

    owner_a = _login(client, email=OWNER_EMAIL)
    client.patch("/api/v1/company/warranty-defaults",
                headers={"X-CSRF-Token": str(owner_a["csrf_token"])},
                json={"labor_days": 90, "parts_days": 30})
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": str(owner_a["csrf_token"])})

    owner_b = _login(client, email="petar@b.bg")
    resp = client.get("/api/v1/company/warranty-defaults",
                      headers={"X-CSRF-Token": str(owner_b["csrf_token"])})
    assert resp.json() == {"labor_days": None, "parts_days": None, **_BLANK_TERMS}


def test_me_exposes_warranty_defaults_to_any_authenticated_user(client: TestClient) -> None:
    """Not owner-gated on /auth/me (unlike the dedicated GET above) — any
    technician opening the delivery dialog or adding a part needs this for
    prefill, the same reason active_modules already rides on /me."""
    company_id = _seed_owner()
    owner_me = _login(client)
    client.patch("/api/v1/company/warranty-defaults",
                headers={"X-CSRF-Token": str(owner_me["csrf_token"])},
                json={"labor_days": 90, "parts_days": 30})
    client.post("/api/v1/users", headers={"X-CSRF-Token": str(owner_me["csrf_token"])},
               json={"name": "Иво", "email": "ivo@a.bg", "password": "парола-за-иво-123"})
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": str(owner_me["csrf_token"])})

    worker_me = _login(client, email="ivo@a.bg", password="парола-за-иво-123")
    assert worker_me["warranty_defaults"] == {"labor_days": 90, "parts_days": 30, **_BLANK_TERMS}
    assert company_id
