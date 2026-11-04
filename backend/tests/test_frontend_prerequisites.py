"""The three FDD backend prerequisites (docs/15 §10): GET /users, GET /dashboard,
GET /search — plus the transition-matrix.json drift check (docs/15 §9)."""

import json
import os
from pathlib import Path

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
        seed_company(db, company, "Мария", email, "парола-123", "1234")
    me = client.post("/api/v1/auth/login",
                     json={"email": email, "password": "парола-123"}).json()
    return {"X-CSRF-Token": str(me["csrf_token"])}


def _add_worker(email: str, name: str = "Иво", active: bool = True) -> str:
    from sqlalchemy import select

    from business_os.identity import security
    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == "a@a.bg"))
        assert owner is not None
        worker = User(company_id=owner.company_id, name=name, email=email,
                      password_hash=security.hash_secret("x"), is_active=active)
        db.add(worker)
        db.commit()
        return str(worker.id)
    raise AssertionError


# --- GET /users --------------------------------------------------------------

def test_users_list_active_only_by_default(client: TestClient) -> None:
    _login(client)
    _add_worker("ivo@a.bg", "Иво")
    inactive_id = _add_worker("star@a.bg", "Бивш", active=False)

    users = client.get("/api/v1/users").json()
    names = [u["name"] for u in users]
    assert names == ["Иво", "Мария"]  # ordered by name, inactive hidden

    all_users = client.get("/api/v1/users?include_inactive=true").json()
    assert inactive_id in [u["id"] for u in all_users]


def test_users_are_tenant_isolated(client: TestClient) -> None:
    _login(client, "Сервиз А", "a@a.bg")
    _add_worker("ivo@a.bg")

    _login(client, "Сервиз Б", "b@b.bg")  # new session cookie replaces A's
    names = [u["name"] for u in client.get("/api/v1/users").json()]
    assert names == ["Мария"]  # only company B's own seeded owner


# --- GET /dashboard ----------------------------------------------------------

def test_dashboard_counts(client: TestClient) -> None:
    from datetime import UTC, datetime, timedelta

    h = _login(client)
    today = datetime.now(UTC).date()  # server computes "today" in UTC, not local wall-clock
    cid = client.post("/api/v1/customers", headers=h,
                      json={"name": "Иван", "phone": "0888111222"}).json()["id"]

    # order-workflow-revamp WP-D (Q6): an asset can have at most one open
    # order now — each call below needs its own asset to have several open
    # simultaneously, exactly as a real dashboard would (four different
    # customers' devices, not one device with four parallel repairs).
    def order(**extra: object) -> str:
        new_aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
            "asset_type_code": "other", "field_values": {"description": "Apple"},
        }).json()["id"]
        return str(client.post("/api/v1/orders", headers=h, json={
            "customer_id": cid, "asset_id": new_aid, "complaint": "x", **extra,
        }).json()["id"])

    o1 = order()  # received
    o2 = order()
    client.post(f"/api/v1/orders/{o2}/status", headers=h, json={"to": "waiting_parts"})
    o3 = order()
    client.post(f"/api/v1/orders/{o3}/status", headers=h, json={"to": "ready"})
    overdue_date = (today - timedelta(days=3)).isoformat()
    order(promised_on=overdue_date)  # overdue: promised past, still received

    client.post(f"/api/v1/orders/{o1}/tasks", headers=h, json={
        "title": "Обади се", "is_call": True,
    })
    client.post(f"/api/v1/orders/{o1}/tasks", headers=h, json={
        "title": "За днес", "due_on": today.isoformat(),
    })

    d = client.get("/api/v1/dashboard").json()
    assert d["active_orders"] == 4
    assert d["waiting_parts"] == 1
    assert d["ready"] == {"count": 1, "over_limit": 0}
    assert d["overdue"] == 1
    assert d["today_tasks"] == 1
    assert d["call_tasks"] == 1


def test_dashboard_empty_company(client: TestClient) -> None:
    _login(client)
    d = client.get("/api/v1/dashboard").json()
    assert d == {"active_orders": 0, "waiting_parts": 0,
                 "ready": {"count": 0, "over_limit": 0}, "overdue": 0,
                 "today_tasks": 0, "call_tasks": 0}


# --- GET /search -------------------------------------------------------------

def _seed_vehicle_type_without_automotive_mileage_gate(email: str) -> None:
    """order-workflow-revamp WP-C (Q18): generic_repair no longer seeds a
    "vehicle" type — this file's searches need one (VIN/reg-№ identifier
    search), but must NOT flip the company to automotive_repair, which
    requires mileage at order creation (Cleanup batch Issue 26) and would
    break _seed_searchables' mileage-less order. AssetType.business_profile
    is just a descriptive tag on the row — only
    `companies.settings.repairflow.business_profile` (untouched here)
    drives the mileage gate, so seeding the type alone is safe."""
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import bind_tenant_scope, open_session
    from serviceflow.assets.models import AssetType
    from serviceflow.assets.service import seed_default_types

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == email))
        assert owner is not None
        bind_tenant_scope(db, owner.company_id)
        already = db.scalar(select(AssetType).where(
            AssetType.company_id == owner.company_id, AssetType.code == "vehicle",
        ))
        if already is None:
            seed_default_types(db, owner.company_id, "automotive_repair")
        db.commit()


def _seed_searchables(client: TestClient, h: dict[str, str],
                      email: str = "a@a.bg") -> dict[str, str]:
    _seed_vehicle_type_without_automotive_mileage_gate(email)
    cid = client.post("/api/v1/customers", headers=h, json={
        "name": "Иван Петров", "phone": "+359 88 812 3456",
    }).json()["id"]
    aid = client.post(f"/api/v1/customers/{cid}/assets", headers=h, json={
        "asset_type_code": "vehicle",
        "field_values": {"brand": "Volkswagen", "model": "Golf", "vin": "WVWZZZ1JZ3W386752",
                         "reg_no": "ВН 1234 АК"},
    }).json()["id"]
    o = client.post("/api/v1/orders", headers=h, json={
        "customer_id": cid, "asset_id": aid, "complaint": "Скърца",
    }).json()
    return {"cid": cid, "aid": aid, "oid": o["id"], "number": o["number"]}


def test_search_by_name_both_alphabets(client: TestClient) -> None:
    h = _login(client)
    _seed_searchables(client, h)
    for q in ("Иван", "ivan", "петров"):
        r = client.get(f"/api/v1/search?q={q}").json()
        assert [c["name"] for c in r["customers"]] == ["Иван Петров"], q


def test_search_by_phone_fragment(client: TestClient) -> None:
    h = _login(client)
    _seed_searchables(client, h)
    r = client.get("/api/v1/search?q=0888123").json()
    assert len(r["customers"]) == 1


def test_search_by_order_number_fragment(client: TestClient) -> None:
    h = _login(client)
    ids = _seed_searchables(client, h)
    fragment = ids["number"][-5:]  # "00001"
    r = client.get(f"/api/v1/search?q={fragment}").json()
    assert [o["number"] for o in r["orders"]] == [ids["number"]]
    assert r["orders"][0]["customer_name"] == "Иван Петров"


def test_search_by_identifier_formats(client: TestClient) -> None:
    h = _login(client)
    ids = _seed_searchables(client, h)
    # VIN fragment and reg number with spaces/lowercase both normalize.
    for q in ("1JZ3W38", "вн 1234", "ВН1234АК"):
        r = client.get(f"/api/v1/search?q={q}").json()
        assert [a["id"] for a in r["assets"]] == [ids["aid"]], q
        assert r["assets"][0]["customer_name"] == "Иван Петров"


def test_search_short_query_returns_empty(client: TestClient) -> None:
    h = _login(client)
    _seed_searchables(client, h)
    r = client.get("/api/v1/search?q=и").json()
    assert r == {"customers": [], "orders": [], "assets": []}


def test_search_is_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    _seed_searchables(client, h_a)
    client.post("/api/v1/auth/logout", headers=h_a)

    _login(client, "Сервиз Б", "b@b.bg")
    r = client.get("/api/v1/search?q=Иван").json()
    assert r == {"customers": [], "orders": [], "assets": []}


# --- transition-matrix.json drift check (docs/15 §9) -------------------------

def test_committed_matrix_json_matches_statuses_py() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
    from export_transition_matrix import build_export

    committed = json.loads(
        (Path(__file__).parents[2] / "frontend" / "src" / "generated"
         / "transition-matrix.json").read_text(encoding="utf-8")
    )
    assert committed == build_export(), (
        "transition-matrix.json is stale — run: "
        "uv run python scripts/export_transition_matrix.py"
    )
