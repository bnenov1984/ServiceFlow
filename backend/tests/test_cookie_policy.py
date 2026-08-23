"""Session-cookie SameSite/Secure policy (business_os/shared_kernel/cookies.py)
for a cross-origin deployment — frontend and backend as separate Render
services. Covers both cookie-issuing planes: tenant (`sf_session`,
identity/router.py) and Vendor Control Plane (`sf_platform_session`,
platform_admin/router.py).

The unit tests below need no DB and always run. The HTTP-level tests exercise
real login/logout against Postgres, same skip gate as test_auth.py /
test_vendor_security.py.
"""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from business_os.shared_kernel.cookies import session_cookie_policy


def test_debug_policy_is_lax_and_insecure() -> None:
    """localhost is plain HTTP — a Secure cookie would just never be sent."""
    assert session_cookie_policy(debug=True) == {"secure": False, "samesite": "lax"}


def test_production_policy_is_none_and_secure() -> None:
    """SameSite=None is what makes the cookie attach to a cross-origin
    fetch(); browsers refuse SameSite=None without Secure, so both change
    together."""
    assert session_cookie_policy(debug=False) == {"secure": True, "samesite": "none"}


pytestmark_db = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


@pytest.fixture
def prod_client(migrated_db: str, tmp_path) -> Iterator[TestClient]:  # noqa: ANN001
    """Same shape as conftest's `client` fixture, except SERVICEFLOW_DEBUG is
    left false — the production cookie path (Secure, SameSite=None)."""
    from sqlalchemy import text

    from business_os.shared_kernel.db import get_engine
    from business_os.shared_kernel.storage import get_local_storage
    from serviceflow.config import get_settings
    from serviceflow.main import create_app

    os.environ["SERVICEFLOW_DATABASE_URL"] = migrated_db
    os.environ["SERVICEFLOW_DEBUG"] = "false"
    os.environ["SERVICEFLOW_DATA_DIR"] = str(tmp_path)
    get_settings.cache_clear()
    get_local_storage.cache_clear()

    with TestClient(create_app(), base_url="https://testserver") as c:
        yield c

    os.environ["SERVICEFLOW_DEBUG"] = "true"  # restore conftest's own default

    assert os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is not None
    engine = get_engine(os.environ["SERVICEFLOW_TEST_DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE contact_records, attachments, tasks, timeline_events, "
            "accessory_items, labor_lines, part_lines, diagnoses, service_orders, "
            "document_sequences, asset_identifiers, assets, customers, audit_log, "
            "platform_audit_log, platform_admin_sessions, platform_admins, "
            "sessions, users, companies RESTART IDENTITY CASCADE"
        ))
    get_settings.cache_clear()
    get_local_storage.cache_clear()


def _tenant_cookie_headers(client: TestClient, *, logout: bool = False) -> list[str]:
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, "Сервиз А", "Мария", "maria@a.bg", "парола-123", "1234")

    resp = client.post(
        "/api/v1/auth/login", json={"email": "maria@a.bg", "password": "парола-123"}
    )
    assert resp.status_code == 200, resp.text
    if not logout:
        return resp.headers.get_list("set-cookie")

    csrf = str(resp.json()["csrf_token"])
    logout_resp = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout_resp.status_code == 200
    return logout_resp.headers.get_list("set-cookie")


@pytestmark_db
def test_tenant_login_cookie_is_lax_and_insecure_in_debug(client: TestClient) -> None:
    headers = _tenant_cookie_headers(client)
    (cookie,) = [h for h in headers if h.startswith("sf_session=")]
    assert "samesite=lax" in cookie.lower()
    assert "secure" not in cookie.lower()


@pytestmark_db
def test_tenant_login_cookie_is_none_and_secure_in_production(prod_client: TestClient) -> None:
    headers = _tenant_cookie_headers(prod_client)
    (cookie,) = [h for h in headers if h.startswith("sf_session=")]
    assert "samesite=none" in cookie.lower()
    assert "secure" in cookie.lower()


@pytestmark_db
def test_tenant_logout_deletes_cookie_with_matching_attributes_in_production(
    prod_client: TestClient,
) -> None:
    headers = _tenant_cookie_headers(prod_client, logout=True)
    (cookie,) = [h for h in headers if h.startswith("sf_session=")]
    assert "samesite=none" in cookie.lower()
    assert "secure" in cookie.lower()
    assert "path=/" in cookie.lower()


def _vendor_cookie_headers(client: TestClient, *, logout: bool = False) -> list[str]:
    from business_os.platform_admin.service import create_platform_admin
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        create_platform_admin(
            db, "Vendor Admin", "vendor.admin@business-os.bg", "вендор-парола-123",
        )

    resp = client.post(
        "/api/v1/platform-admin/auth/login",
        json={"email": "vendor.admin@business-os.bg", "password": "вендор-парола-123"},
    )
    assert resp.status_code == 200, resp.text
    if not logout:
        return resp.headers.get_list("set-cookie")

    csrf = str(resp.json()["csrf_token"])
    logout_resp = client.post(
        "/api/v1/platform-admin/auth/logout", headers={"X-CSRF-Token": csrf}
    )
    assert logout_resp.status_code == 200
    return logout_resp.headers.get_list("set-cookie")


@pytestmark_db
def test_vendor_login_cookie_is_lax_and_insecure_in_debug(client: TestClient) -> None:
    headers = _vendor_cookie_headers(client)
    (cookie,) = [h for h in headers if h.startswith("sf_platform_session=")]
    assert "samesite=lax" in cookie.lower()
    assert "secure" not in cookie.lower()


@pytestmark_db
def test_vendor_login_cookie_is_none_and_secure_in_production(prod_client: TestClient) -> None:
    headers = _vendor_cookie_headers(prod_client)
    (cookie,) = [h for h in headers if h.startswith("sf_platform_session=")]
    assert "samesite=none" in cookie.lower()
    assert "secure" in cookie.lower()


@pytestmark_db
def test_vendor_logout_deletes_cookie_with_matching_attributes_in_production(
    prod_client: TestClient,
) -> None:
    headers = _vendor_cookie_headers(prod_client, logout=True)
    (cookie,) = [h for h in headers if h.startswith("sf_platform_session=")]
    assert "samesite=none" in cookie.lower()
    assert "secure" in cookie.lower()
    assert "path=/api/v1/platform-admin" in cookie.lower()
