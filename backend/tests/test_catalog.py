"""CatalogItem CRUD, Owner-only mutations, code uniqueness, CSV/Excel import
(dry-run preview + commit), tenant isolation (docs/12 §1 P0-9) — ADR-BOS-013,
order-workflow-revamp WP-I."""

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


def _worker_headers(client: TestClient, email: str = "a@a.bg") -> dict[str, str]:
    """A second, non-Owner user in the same company as `_login`'s Owner."""
    from sqlalchemy import select

    from business_os.identity import security
    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    worker_email = "worker-" + email
    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        owner = db.scalar(select(User).where(User.email == email))
        assert owner is not None
        existing = db.scalar(select(User).where(User.email == worker_email))
        if existing is None:
            worker = User(company_id=owner.company_id, name="Worker", email=worker_email,
                          password_hash=security.hash_secret("парола-123"))
            db.add(worker)
            db.commit()
    me = client.post("/api/v1/auth/login",
                     json={"email": worker_email, "password": "парола-123"}).json()
    return {"X-CSRF-Token": str(me["csrf_token"])}


def test_owner_creates_and_lists_item(client: TestClient) -> None:
    h = _login(client)
    r = client.post("/api/v1/catalog-items", headers=h, json={
        "kind": "part", "name": "Дисплей", "unit": "pcs", "sale_price": "85.00",
        "code": "D-1", "unit_cost": "50.00",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Дисплей"
    assert body["code"] == "D-1"
    assert body["unit_cost"] == 50.0
    assert body["archived"] is False

    items = client.get("/api/v1/catalog-items", headers=h).json()
    assert len(items) == 1
    assert items[0]["id"] == body["id"]


def test_worker_can_read_but_not_create(client: TestClient) -> None:
    # Identity here is carried by the TestClient's shared session cookie, not
    # the `headers` dict, so owner actions must happen before _worker_headers
    # switches that cookie over to the worker's session.
    h_owner = _login(client)
    client.post("/api/v1/catalog-items", headers=h_owner, json={
        "kind": "part", "name": "Дисплей", "unit": "pcs", "sale_price": "85",
    })

    h_worker = _worker_headers(client)
    r = client.post("/api/v1/catalog-items", headers=h_worker, json={
        "kind": "part", "name": "Дисплей", "unit": "pcs", "sale_price": "85",
    })
    assert r.status_code == 403

    items = client.get("/api/v1/catalog-items", headers=h_worker).json()
    assert len(items) == 1


def test_unit_cost_hidden_from_a_non_owner_caller(client: TestClient) -> None:
    # Same cookie-ordering caveat as above: do the owner's post+get first.
    h_owner = _login(client)
    client.post("/api/v1/catalog-items", headers=h_owner, json={
        "kind": "part", "name": "Дисплей", "unit": "pcs", "sale_price": "85",
        "unit_cost": "50",
    })
    as_owner = client.get("/api/v1/catalog-items", headers=h_owner).json()
    assert as_owner[0]["unit_cost"] == 50.0

    h_worker = _worker_headers(client)
    as_worker = client.get("/api/v1/catalog-items", headers=h_worker).json()
    assert as_worker[0]["unit_cost"] is None


def test_duplicate_code_rejected(client: TestClient) -> None:
    h = _login(client)
    client.post("/api/v1/catalog-items", headers=h, json={
        "kind": "part", "name": "Дисплей", "unit": "pcs", "sale_price": "85", "code": "D-1",
    })
    r = client.post("/api/v1/catalog-items", headers=h, json={
        "kind": "part", "name": "Друг дисплей", "unit": "pcs", "sale_price": "90", "code": "D-1",
    })
    assert r.status_code == 409
    assert r.json()["detail"]["message_key"] == "errors.catalog.code_conflict"


def test_patch_updates_fields_and_respects_code_uniqueness(client: TestClient) -> None:
    h = _login(client)
    item_id = client.post("/api/v1/catalog-items", headers=h, json={
        "kind": "part", "name": "Дисплей", "unit": "pcs", "sale_price": "85",
    }).json()["id"]
    other_id = client.post("/api/v1/catalog-items", headers=h, json={
        "kind": "part", "name": "Батерия", "unit": "pcs", "sale_price": "20", "code": "B-1",
    }).json()["id"]

    r = client.patch(f"/api/v1/catalog-items/{item_id}", headers=h, json={"sale_price": "99.00"})
    assert r.status_code == 200
    assert r.json()["sale_price"] == 99.0

    conflict = client.patch(f"/api/v1/catalog-items/{item_id}", headers=h, json={"code": "B-1"})
    assert conflict.status_code == 409

    assert client.patch(f"/api/v1/catalog-items/{other_id}", headers=h,
                        json={"code": "B-1"}).status_code == 200


def test_archive_and_unarchive_roundtrip(client: TestClient) -> None:
    h = _login(client)
    item_id = client.post("/api/v1/catalog-items", headers=h, json={
        "kind": "part", "name": "Дисплей", "unit": "pcs", "sale_price": "85",
    }).json()["id"]

    archived = client.post(f"/api/v1/catalog-items/{item_id}/archive", headers=h).json()
    assert archived["archived"] is True

    default_list = client.get("/api/v1/catalog-items", headers=h).json()
    assert default_list == []
    full_list = client.get("/api/v1/catalog-items?include_archived=true", headers=h).json()
    assert len(full_list) == 1

    unarchived = client.post(f"/api/v1/catalog-items/{item_id}/unarchive", headers=h).json()
    assert unarchived["archived"] is False
    assert len(client.get("/api/v1/catalog-items", headers=h).json()) == 1


def test_kind_filter(client: TestClient) -> None:
    h = _login(client)
    client.post("/api/v1/catalog-items", headers=h, json={
        "kind": "part", "name": "Дисплей", "unit": "pcs", "sale_price": "85",
    })
    client.post("/api/v1/catalog-items", headers=h, json={
        "kind": "labor", "name": "Труд", "unit": "pcs", "sale_price": "20",
    })

    parts = client.get("/api/v1/catalog-items?kind=part", headers=h).json()
    assert [i["name"] for i in parts] == ["Дисплей"]
    labor = client.get("/api/v1/catalog-items?kind=labor", headers=h).json()
    assert [i["name"] for i in labor] == ["Труд"]


def test_catalog_items_are_tenant_isolated(client: TestClient) -> None:
    h_a = _login(client, "Сервиз А", "a@a.bg")
    item_id = client.post("/api/v1/catalog-items", headers=h_a, json={
        "kind": "part", "name": "Дисплей", "unit": "pcs", "sale_price": "85",
    }).json()["id"]
    client.post("/api/v1/auth/logout", headers=h_a)

    h_b = _login(client, "Сервиз Б", "b@b.bg")
    assert client.get("/api/v1/catalog-items", headers=h_b).json() == []
    assert client.patch(f"/api/v1/catalog-items/{item_id}", headers=h_b,
                        json={"sale_price": "1"}).status_code == 404


# --- CSV/Excel import --------------------------------------------------------

def _csv_upload(client: TestClient, h: dict[str, str], path: str, content: str) -> object:
    files = {"file": ("price-list.csv", content.encode("utf-8"), "text/csv")}
    return client.post(path, headers=h, files=files)


def test_import_preview_classifies_insert_update_and_error_rows(client: TestClient) -> None:
    h = _login(client)
    client.post("/api/v1/catalog-items", headers=h, json={
        "kind": "part", "name": "Стар дисплей", "unit": "pcs", "sale_price": "70", "code": "D-1",
    })

    csv_body = (
        "kind,name,code,unit,sale_price,unit_cost\n"
        "част,Нов дисплей,D-1,бр.,85.00,50.00\n"  # matches existing code -> update
        "труд,Диагностика,,бр.,20.00,\n"           # new, no code -> insert
        "невалиден,Нещо,,бр.,10,\n"                # invalid kind -> error
    )
    r = _csv_upload(client, h, "/api/v1/catalog-items/import/preview", csv_body)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["insert_count"] == 1
    assert body["update_count"] == 1
    assert body["error_count"] == 1
    actions = {row["row_number"]: row["action"] for row in body["rows"]}
    assert actions == {1: "update", 2: "insert", 3: "error"}
    assert body["rows"][2]["error"] == "errors.catalog.import_invalid_kind"

    # Preview never writes.
    assert len(client.get("/api/v1/catalog-items", headers=h).json()) == 1


def test_import_commit_applies_inserts_and_updates_skips_errors(client: TestClient) -> None:
    h = _login(client)
    client.post("/api/v1/catalog-items", headers=h, json={
        "kind": "part", "name": "Стар дисплей", "unit": "pcs", "sale_price": "70", "code": "D-1",
    })

    csv_body = (
        "kind,name,code,unit,sale_price,unit_cost\n"
        "част,Нов дисплей,D-1,бр.,85.00,\n"
        "труд,Диагностика,,бр.,20.00,\n"
        "невалиден,Нещо,,бр.,10,\n"
    )
    r = _csv_upload(client, h, "/api/v1/catalog-items/import/commit", csv_body)
    assert r.status_code == 200, r.text

    items = client.get("/api/v1/catalog-items", headers=h).json()
    assert len(items) == 2  # the error row was skipped, not applied
    by_code = {i["code"]: i for i in items if i["code"]}
    assert by_code["D-1"]["name"] == "Нов дисплей"
    assert by_code["D-1"]["sale_price"] == 85.0
    assert any(i["name"] == "Диагностика" for i in items)


def test_import_rejects_two_new_rows_sharing_the_same_code(client: TestClient) -> None:
    """A code that doesn't match any *existing* row but repeats twice in the
    file itself would otherwise classify both as "insert" and collide on the
    (company_id, code) unique index at commit — caught here instead."""
    h = _login(client)
    csv_body = (
        "kind,name,code,unit,sale_price,unit_cost\n"
        "част,Дисплей А,DUP,бр.,85.00,\n"
        "част,Дисплей Б,DUP,бр.,90.00,\n"
    )
    r = _csv_upload(client, h, "/api/v1/catalog-items/import/preview", csv_body)
    body = r.json()
    assert body["insert_count"] == 1
    assert body["error_count"] == 1
    assert body["rows"][1]["error"] == "errors.catalog.import_duplicate_code_in_file"

    commit = _csv_upload(client, h, "/api/v1/catalog-items/import/commit", csv_body)
    assert commit.status_code == 200, commit.text
    items = client.get("/api/v1/catalog-items", headers=h).json()
    assert len(items) == 1
    assert items[0]["name"] == "Дисплей А"


def test_import_worker_forbidden(client: TestClient) -> None:
    _login(client)
    h_worker = _worker_headers(client)
    r = _csv_upload(client, h_worker, "/api/v1/catalog-items/import/preview",
                    "kind,name,code,unit,sale_price,unit_cost\nчаст,X,,бр.,1,\n")
    assert r.status_code == 403


def test_import_accepts_english_headers_too(client: TestClient) -> None:
    h = _login(client)
    csv_body = "kind,name,code,unit,sale_price,unit_cost\npart,Display,,pcs,85.00,\n"
    r = _csv_upload(client, h, "/api/v1/catalog-items/import/commit", csv_body)
    assert r.status_code == 200, r.text
    items = client.get("/api/v1/catalog-items", headers=h).json()
    assert items[0]["kind"] == "part"
    assert items[0]["unit"] == "pcs"
