"""Cleanup batch Issue 7: the server, not just the frontend prefill, applies
the company's configured labor/parts warranty defaults when a client omits
`warranty_days`. Semantics: NULL/omitted = unspecified, 0 = explicitly no
warranty (never replaced by a default), positive = an explicit duration.
See commercial... no — serviceflow.service_orders.service.change_status()'s
"delivered" branch and serviceflow.service_orders.lines.add_part_line()."""

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


def _set_warranty_defaults(client: TestClient, h: dict[str, str],
                          labor_days: int | None = None, parts_days: int | None = None) -> None:
    body: dict[str, object] = {}
    if labor_days is not None:
        body["labor_days"] = labor_days
    if parts_days is not None:
        body["parts_days"] = parts_days
    resp = client.patch("/api/v1/company/warranty-defaults", headers=h, json=body)
    assert resp.status_code == 200, resp.text


def _customer_and_asset(client: TestClient, h: dict[str, str]) -> tuple[str, str]:
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": "0888111222"}).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "other", "field_values": {"description": "Apple"},
    }).json()["id"]
    return cid, aid


def _order(client: TestClient, h: dict[str, str], cid: str, aid: str) -> str:
    r = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Не се включва",
    })
    assert r.status_code == 201, r.text
    return str(r.json()["id"])



def _deliver(client: TestClient, h: dict[str, str], oid: str,
            warranty_days: int | None = None, skip: bool = True) -> "object":
    for to in ("diagnostics", "repair", "ready"):
        client.post(f"/api/v1/orders/{oid}/status", headers=h, json={"to": to})
    body: dict[str, object] = {"to": "completed"}
    if warranty_days is not None:
        body["warranty_days"] = warranty_days
    return client.post(f"/api/v1/orders/{oid}/status", headers=h, json=body)


# --- Labor / work warranty --------------------------------------------------


def test_omitted_labor_warranty_uses_company_default(client: TestClient) -> None:
    h = _login(client)
    _set_warranty_defaults(client, h, labor_days=30)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)

    resp = _deliver(client, h, oid)
    assert resp.status_code == 200, resp.text
    assert resp.json()["warranty_days"] == 30


def test_explicit_labor_warranty_zero_is_preserved_not_replaced_by_default(
    client: TestClient,
) -> None:
    h = _login(client)
    _set_warranty_defaults(client, h, labor_days=30)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)

    resp = _deliver(client, h, oid, warranty_days=0)
    assert resp.status_code == 200, resp.text
    assert resp.json()["warranty_days"] == 0


def test_explicit_positive_labor_warranty_wins_over_default(client: TestClient) -> None:
    h = _login(client)
    _set_warranty_defaults(client, h, labor_days=30)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)

    resp = _deliver(client, h, oid, warranty_days=90)
    assert resp.status_code == 200, resp.text
    assert resp.json()["warranty_days"] == 90


def test_omitted_labor_warranty_stays_null_when_no_company_default(client: TestClient) -> None:
    h = _login(client)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)

    resp = _deliver(client, h, oid)
    assert resp.status_code == 200, resp.text
    assert resp.json()["warranty_days"] is None


def test_labor_default_captured_into_completion_snapshot(client: TestClient) -> None:
    h = _login(client)
    _set_warranty_defaults(client, h, labor_days=45)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)
    _deliver(client, h, oid)

    r = client.get(f"/api/v1/orders/{oid}/protocol.pdf?type=delivery", headers=h)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")

    import io

    from pypdf import PdfReader
    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(r.content)).pages)
    assert "45" in text


def test_later_company_default_change_does_not_mutate_already_delivered_warranty(
    client: TestClient,
) -> None:
    h = _login(client)
    _set_warranty_defaults(client, h, labor_days=30)
    cid, aid = _customer_and_asset(client, h)
    oid = _order(client, h, cid, aid)
    _deliver(client, h, oid)

    body = client.get(f"/api/v1/orders/{oid}", headers=h).json()
    assert body["warranty_days"] == 30

    # Owner changes the company default afterward.
    _set_warranty_defaults(client, h, labor_days=90)

    after = client.get(f"/api/v1/orders/{oid}", headers=h).json()
    assert after["warranty_days"] == 30

# order-workflow-revamp WP-J retired per-part warranty inheritance from the
# company's `parts_days` default entirely — `PartLine.has_warranty` is now a
# plain boolean that always defaults to `true` (Q14c) regardless of any
# company setting; see test_order_operations.py's
# test_part_line_has_warranty_defaults_to_true_and_can_be_toggled for its
# coverage. `parts_days` itself still exists as a company setting (read by
# the frontend for display, folded into the protocol's company-wide
# warranty text) — just no longer inherited onto individual lines.
