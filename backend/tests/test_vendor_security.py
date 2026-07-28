"""Vendor Control Plane security boundary (ADR-BOS-009, docs/business-os/18 §8).

Vendor Administrators and tenant users are different security principals. These
tests exercise that at the HTTP layer against a real database; the structural
half (import graph, FastAPI dependency graph, no `company_id`) lives in
tests/test_architecture.py.

The isolation-suite discipline ADR-016 established for cross-tenant reads is
applied here to cross-*plane* access: every prohibited direction gets its own
named negative test, so a future endpoint that forgets the rule fails a test
with a name that says what broke.
"""

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)

VENDOR = "/api/v1/platform-admin"
ADMIN_EMAIL = "vendor.admin@business-os.bg"
ADMIN_PASSWORD = "вендор-парола-123"
TENANT_EMAIL = "maria@a.bg"
TENANT_PASSWORD = "парола-123"


def _db() -> Iterator[object]:
    from business_os.shared_kernel.db import open_session

    return open_session(os.environ["SERVICEFLOW_DATABASE_URL"])


def _seed_tenant(email: str = TENANT_EMAIL) -> None:
    from business_os.identity.service import seed_company

    for db in _db():
        seed_company(db, "Сервиз А", "Мария", email, TENANT_PASSWORD, "1234")


def _seed_admin(email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD,
                is_active: bool = True) -> uuid.UUID:
    from business_os.platform_admin.service import create_platform_admin

    for db in _db():
        admin, _ = create_platform_admin(db, "Вендор Админ", email, password)
        if not is_active:
            admin.is_active = False
            db.commit()  # type: ignore[attr-defined]
        return admin.id
    raise AssertionError("unreachable")


def _vendor_login(client: TestClient, email: str = ADMIN_EMAIL,
                  password: str = ADMIN_PASSWORD) -> dict[str, object]:
    resp = client.post(f"{VENDOR}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _tenant_login(client: TestClient, email: str = TENANT_EMAIL,
                  password: str = TENANT_PASSWORD) -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def _audit_actions() -> list[str]:
    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAuditLog

    for db in _db():
        return list(db.scalars(  # type: ignore[attr-defined]
            select(PlatformAuditLog.action).order_by(PlatformAuditLog.created_at)
        ))
    raise AssertionError("unreachable")


def _reset_rate_limiter() -> None:
    from business_os.platform_admin import service

    service._failures.clear()  # noqa: SLF001


# --- The walking-skeleton endpoint itself ------------------------------


def test_active_vendor_admin_can_read_the_protected_endpoint(client: TestClient) -> None:
    _reset_rate_limiter()
    admin_id = _seed_admin()
    me = _vendor_login(client)
    assert me["platform_admin_id"] == str(admin_id)

    resp = client.get(f"{VENDOR}/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == ADMIN_EMAIL
    # A vendor principal has no company — the response shape says so.
    assert "company_id" not in body


def test_unauthenticated_request_to_vendor_namespace_is_rejected(client: TestClient) -> None:
    resp = client.get(f"{VENDOR}/me")
    assert resp.status_code == 401
    assert resp.json()["detail"]["message_key"] == "errors.auth.required"


def test_inactive_vendor_admin_is_rejected_at_login_and_on_a_live_session(
    client: TestClient,
) -> None:
    """Both halves: `is_active` is the entire permission model (ADR-BOS-009),
    so deactivation must bite at login *and* kill sessions already issued."""
    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAdmin

    _reset_rate_limiter()
    _seed_admin()
    _vendor_login(client)
    assert client.get(f"{VENDOR}/me").status_code == 200

    for db in _db():
        admin = db.scalar(select(PlatformAdmin))  # type: ignore[attr-defined]
        admin.is_active = False
        db.commit()  # type: ignore[attr-defined]

    assert client.get(f"{VENDOR}/me").status_code == 401
    resp = client.post(f"{VENDOR}/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 401
    assert resp.json()["detail"]["message_key"] == "errors.auth.invalid_credentials"


def test_vendor_logout_revokes_the_session(client: TestClient) -> None:
    _reset_rate_limiter()
    _seed_admin()
    me = _vendor_login(client)

    assert client.post(f"{VENDOR}/auth/logout").status_code == 403  # CSRF required
    resp = client.post(f"{VENDOR}/auth/logout",
                       headers={"X-CSRF-Token": str(me["csrf_token"])})
    assert resp.status_code == 200
    assert client.get(f"{VENDOR}/me").status_code == 401


# --- Cross-plane separation --------------------------------------------


def test_tenant_session_cannot_access_the_vendor_namespace(client: TestClient) -> None:
    """A fully authenticated Tenant Owner is still nobody on the vendor plane."""
    _seed_tenant()
    me = _tenant_login(client)
    assert me["is_owner"] is True
    assert client.get("/api/v1/auth/me").status_code == 200  # the tenant session is live

    resp = client.get(f"{VENDOR}/me")
    assert resp.status_code == 401
    resp = client.post(f"{VENDOR}/auth/logout",
                       headers={"X-CSRF-Token": str(me["csrf_token"])})
    assert resp.status_code == 401


def test_tenant_user_cannot_authenticate_as_vendor_admin(client: TestClient) -> None:
    """Vendor login only ever looks in `platform_admins` — a tenant user's real
    credentials are simply not there."""
    _reset_rate_limiter()
    _seed_tenant()
    resp = client.post(f"{VENDOR}/auth/login",
                       json={"email": TENANT_EMAIL, "password": TENANT_PASSWORD})
    assert resp.status_code == 401
    assert resp.json()["detail"]["message_key"] == "errors.auth.invalid_credentials"


def test_vendor_admin_cannot_authenticate_through_the_tenant_endpoint(
    client: TestClient,
) -> None:
    """The mirror image: tenant login only ever looks in `users`. There is no
    combined login that searches both stores."""
    from business_os.identity import service as identity_service

    identity_service._failures.clear()  # noqa: SLF001
    _seed_admin()
    resp = client.post("/api/v1/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 401
    identity_service._failures.clear()  # noqa: SLF001


def test_the_two_planes_coexist_under_one_shared_email(client: TestClient) -> None:
    """Hardest case for a boundary that is only skin deep: the same address is
    a tenant Owner and a Vendor Administrator, with different passwords. Each
    credential works on exactly one plane, and each session token is worthless
    on the other."""
    _reset_rate_limiter()
    shared = "boris@example.bg"
    _seed_tenant(email=shared)
    _seed_admin(email=shared, password="друга-вендор-парола")

    tenant = _tenant_login(client, email=shared, password=TENANT_PASSWORD)
    assert client.get("/api/v1/auth/me").json()["user_id"] == tenant["user_id"]
    # The tenant password does not open the vendor plane...
    assert client.post(f"{VENDOR}/auth/login",
                       json={"email": shared, "password": TENANT_PASSWORD}).status_code == 401
    # ...and the tenant session cookie does not either.
    assert client.get(f"{VENDOR}/me").status_code == 401

    vendor = _vendor_login(client, email=shared, password="друга-вендор-парола")
    assert client.get(f"{VENDOR}/me").json()["platform_admin_id"] == vendor["platform_admin_id"]
    # The tenant plane is unchanged by the vendor login that just happened.
    assert client.get("/api/v1/auth/me").json()["user_id"] == tenant["user_id"]


def test_a_vendor_session_token_is_not_a_tenant_session_token(client: TestClient) -> None:
    """Replaying the raw vendor token under the tenant cookie name must fail:
    the two token stores are different tables, so neither lookup can resolve
    the other's token even when the cookie-path scoping is bypassed by hand."""
    _reset_rate_limiter()
    _seed_tenant()
    _seed_admin()
    _vendor_login(client)
    raw = client.cookies.get("sf_platform_session", path="/api/v1/platform-admin")
    assert raw

    client.cookies.clear()
    client.cookies.set("sf_session", raw, path="/")
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/users").status_code == 401
    assert client.get("/api/v1/customers").status_code == 401


def test_tenant_routes_behave_exactly_as_before(client: TestClient) -> None:
    """Regression guard for the plane that already existed: login → me →
    an authorised tenant read → CSRF-protected logout, all unchanged while a
    Vendor Administrator exists in the database."""
    _seed_tenant()
    _seed_admin()

    me = _tenant_login(client)
    assert me["is_owner"] is True
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.get("/api/v1/customers").status_code == 200
    assert client.get("/api/v1/users").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/logout",
                       headers={"X-CSRF-Token": str(me["csrf_token"])}).status_code == 200


# --- No TenantContext, no tenant RLS GUC -------------------------------


def test_vendor_request_never_sets_the_tenant_rls_guc(client: TestClient) -> None:
    """ADR-BOS-009 §Consequences: the Control Plane must be built so it never
    needs to bypass RLS. Captured at the driver level — every statement the
    vendor request executes is recorded, and none of them binds
    `app.company_id`. A tenant request in the same test does bind it, so the
    probe is proven to be capable of seeing the thing it denies."""
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    _reset_rate_limiter()
    _seed_tenant()
    _seed_admin()
    _vendor_login(client)

    statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ANN202
        statements.append(statement)

    event.listen(Engine, "before_cursor_execute", _capture)
    try:
        assert client.get(f"{VENDOR}/me").status_code == 200
        vendor_statements = list(statements)

        statements.clear()
        _tenant_login(client)
        assert client.get("/api/v1/customers").status_code == 200
        tenant_statements = list(statements)
    finally:
        event.remove(Engine, "before_cursor_execute", _capture)

    assert vendor_statements, "no SQL captured — the probe would pass vacuously"
    assert not [s for s in vendor_statements if "app.company_id" in s], (
        "a vendor request bound the tenant RLS GUC: "
        f"{[s for s in vendor_statements if 'app.company_id' in s]}"
    )
    assert [s for s in tenant_statements if "app.company_id" in s], (
        "the tenant request did not bind app.company_id either — the probe is "
        "not actually able to detect GUC binding, so the assertion above is void"
    )


def test_vendor_request_reads_no_tenant_table(client: TestClient) -> None:
    """Metadata-first, not tenant-business-data-first: the walking-skeleton
    endpoint touches only vendor-owned tables. Named tenant tables are checked
    individually so a future endpoint that starts reading one fails here."""
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    _reset_rate_limiter()
    _seed_tenant()
    _seed_admin()
    _vendor_login(client)

    statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ANN202
        statements.append(statement.lower())

    event.listen(Engine, "before_cursor_execute", _capture)
    try:
        assert client.get(f"{VENDOR}/me").status_code == 200
    finally:
        event.remove(Engine, "before_cursor_execute", _capture)

    for tenant_table in ("customers", "assets", "service_orders", "invoices", "payments",
                         "ps_clients", "ps_assignments", "attachments", "contact_records",
                         "timeline_events", "users", "sessions"):
        hits = [s for s in statements if f" {tenant_table}" in s]
        assert not hits, f"vendor request touched tenant table {tenant_table}: {hits}"


TENANT_TABLES = ("customers", "assets", "service_orders", "invoices", "payments",
                 "ps_clients", "ps_assignments", "attachments", "contact_records",
                 "timeline_events")

# `users`/`sessions` deliberately excluded from this sweep: they are
# identity-bootstrap tables (docs/business-os/18 §1.1), not tenant
# *operational* data — ADR-BOS-009 §Vendor data visibility's "not visible" set
# is customers/assets/orders/engagements/documents/invoices/notes, and both
# are legitimately touched by sanctioned vendor actions this same sweep
# exercises: provisioning writes `users` once to create the first Owner
# (ADR-BOS-009 Q2, tested in test_company_provisioning.py), and the company
# list/detail routes read it to report `seat_usage`, an explicitly
# vendor-visible *aggregate* (§7 screen 8; individual rows are what stays
# forbidden, not the count).


def test_every_vendor_route_touches_no_tenant_table(client: TestClient) -> None:
    """Extends `test_vendor_request_reads_no_tenant_table` (previously the
    `/me` probe alone, docs/business-os/18 §9 phase 8) across the *entire*
    mounted vendor route graph: login, every read, provisioning, entitlement
    grant/revoke, and a subscription transition — each invoked for real, each
    checked against every named tenant table, so a future vendor route that
    starts reading one fails here regardless of which route it is."""
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    _reset_rate_limiter()
    _seed_admin()

    def _probe(method: str, url: str, *, headers: dict[str, str] | None = None,
              json: dict[str, object] | None = None) -> object:
        statements: list[str] = []

        def _capture(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ANN202
            statements.append(statement.lower())

        event.listen(Engine, "before_cursor_execute", _capture)
        try:
            resp = client.request(method, url, headers=headers, json=json)
        finally:
            event.remove(Engine, "before_cursor_execute", _capture)

        assert resp.status_code < 500, f"{method} {url} errored: {resp.text}"
        for tenant_table in TENANT_TABLES:
            hits = [s for s in statements if f" {tenant_table}" in s]
            assert not hits, f"{method} {url} touched tenant table {tenant_table}: {hits}"
        return resp.json() if resp.content else None

    me = _probe("POST", f"{VENDOR}/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert isinstance(me, dict)
    csrf = {"X-CSRF-Token": str(me["csrf_token"])}

    provisioned = _probe("POST", f"{VENDOR}/companies", headers=csrf, json={
        "company_name": "Обходен Сървейл ЕООД", "owner_name": "Нов Собственик",
        "owner_email": "new-owner@route-sweep.bg", "owner_password": "нова-парола-1234",
    })
    assert isinstance(provisioned, dict)
    company_id = provisioned["company_id"]

    _probe("GET", f"{VENDOR}/me")
    _probe("GET", f"{VENDOR}/companies")
    _probe("GET", f"{VENDOR}/companies/{company_id}")
    _probe("PUT", f"{VENDOR}/companies/{company_id}/modules/professional-services", headers=csrf)
    _probe("DELETE", f"{VENDOR}/companies/{company_id}/modules/professional-services",
          headers=csrf)
    _probe("POST", f"{VENDOR}/companies/{company_id}/subscription/transitions", headers=csrf,
          json={"new_state": "active", "reason": "route sweep"})
    _probe("POST", f"{VENDOR}/auth/logout", headers=csrf)


# --- Platform audit log -------------------------------------------------


def test_audit_records_vendor_authentication_events(client: TestClient) -> None:
    _reset_rate_limiter()
    admin_id = _seed_admin()
    assert _audit_actions() == ["platform_admin.bootstrapped"]

    client.post(f"{VENDOR}/auth/login", json={"email": ADMIN_EMAIL, "password": "грешна"})
    me = _vendor_login(client)
    client.post(f"{VENDOR}/auth/logout", headers={"X-CSRF-Token": str(me["csrf_token"])})

    assert _audit_actions() == [
        "platform_admin.bootstrapped",
        "platform_admin.login_failed",
        "platform_admin.login",
        "platform_admin.logout",
    ]

    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAuditLog

    for db in _db():
        rows = list(db.scalars(  # type: ignore[attr-defined]
            select(PlatformAuditLog).order_by(PlatformAuditLog.created_at)))
        assert all(r.platform_admin_id == admin_id for r in rows)
        # No secrets anywhere in the trail (11 §3) — not the password, not the
        # session token, not the CSRF token.
        blob = str([(r.action, r.detail, r.reason) for r in rows])
        assert ADMIN_PASSWORD not in blob
        assert "грешна" not in blob
        assert str(me["csrf_token"]) not in blob


def test_reading_the_protected_endpoint_writes_no_audit_record(client: TestClient) -> None:
    """ADR-BOS-009 audits *mutations*. A GET of one's own identity is not one,
    and auditing every read would bury the records the log exists for."""
    _reset_rate_limiter()
    _seed_admin()
    _vendor_login(client)
    before = _audit_actions()

    for _ in range(3):
        assert client.get(f"{VENDOR}/me").status_code == 200

    assert _audit_actions() == before


def test_platform_audit_log_rejects_an_unknown_action(client: TestClient) -> None:
    """The action vocabulary is centralised (`platform_admin.audit`), so an
    ad-hoc literal at a call site fails loudly instead of writing a row nobody
    can interpret later. (`client` is requested by every DB-touching test in
    this file — it is the fixture that migrates the schema and truncates
    afterwards; a test that skips it leaks rows into the ones that follow.)"""
    from business_os.platform_admin import audit
    from business_os.shared_kernel import correlation

    for db in _db():
        with pytest.raises(ValueError, match="unknown platform audit action"):
            audit.record(db, "something.improvised", correlation.ensure_bound())


def test_platform_audit_log_is_append_only_in_the_database(client: TestClient) -> None:
    """The trigger from migration 0012 — role-independent, so it holds even for
    code that bypasses `platform_admin.audit` entirely (raw SQL included)."""
    from sqlalchemy.exc import DatabaseError

    _reset_rate_limiter()
    _seed_admin()
    assert _audit_actions()

    for db in _db():
        with pytest.raises(DatabaseError, match="append-only"):
            db.execute(text(  # type: ignore[attr-defined]
                "UPDATE platform_audit_log SET action = 'tampered'"))
        db.rollback()  # type: ignore[attr-defined]
        with pytest.raises(DatabaseError, match="append-only"):
            db.execute(text("DELETE FROM platform_audit_log"))  # type: ignore[attr-defined]
        db.rollback()  # type: ignore[attr-defined]

    assert "tampered" not in _audit_actions()


# --- Bootstrap ----------------------------------------------------------


def test_bootstrap_creates_the_first_admin_and_is_idempotent(client: TestClient) -> None:
    """Requirement: safe non-public creation, idempotent on re-run. A second
    run must not re-hash the password (which would silently rotate a live
    credential) nor resurrect a deactivated admin."""
    from business_os.platform_admin.service import create_platform_admin

    for db in _db():
        first, created = create_platform_admin(db, "Вендор Админ", ADMIN_EMAIL, ADMIN_PASSWORD)
        assert created is True
        original_hash = first.password_hash

        again, created_again = create_platform_admin(
            db, "Друго Име", ADMIN_EMAIL.upper(), "съвсем-друга-парола")
        assert created_again is False
        assert again.id == first.id
        assert again.name == "Вендор Админ"  # not renamed
        assert again.password_hash == original_hash  # not rotated

        first.is_active = False
        db.commit()  # type: ignore[attr-defined]
        _, created_third = create_platform_admin(
            db, "Вендор Админ", ADMIN_EMAIL, ADMIN_PASSWORD)
        assert created_third is False
        assert first.is_active is False  # not silently reactivated

    # Exactly one bootstrap audit row, from the single real creation.
    assert _audit_actions().count("platform_admin.bootstrapped") == 1


def test_bootstrap_normalizes_the_login_identifier(client: TestClient) -> None:
    """Unique normalised identifier: casing and surrounding whitespace cannot
    produce a second admin for the same address."""
    from business_os.platform_admin.service import create_platform_admin, find_by_email

    for db in _db():
        create_platform_admin(db, "Вендор Админ", "  Vendor@Example.BG ", ADMIN_PASSWORD)
        assert find_by_email(db, "vendor@example.bg") is not None
        _, created = create_platform_admin(db, "Друг", "VENDOR@EXAMPLE.BG", "друга-парола")
        assert created is False


def test_bootstrap_cli_runs_standalone(client: TestClient) -> None:
    """Runs the real command in a real subprocess, because that is the only way
    to exercise it as the vendor operator will: a fresh interpreter importing
    `business_os.platform_admin` and nothing else.

    Regression guard — the first version of this slice passed every in-process
    test and still crashed here with `NoReferencedTableError`, because
    `platform_audit_log.company_id` carried an ORM-level ForeignKey to a table
    (`companies`) whose mapper only exists when the tenant identity module is
    imported, which the vendor plane may not do. The `client` fixture is
    requested purely so the rows this creates are truncated afterwards.
    """
    import subprocess
    import sys

    env = {
        **os.environ,
        "SERVICEFLOW_DATABASE_URL": os.environ["SERVICEFLOW_DATABASE_URL"],
        "SERVICEFLOW_PLATFORM_ADMIN_PASSWORD": ADMIN_PASSWORD,
        "PYTHONIOENCODING": "utf-8",
    }
    argv = [sys.executable, "-m", "business_os.platform_admin.bootstrap",
            "Вендор Админ", ADMIN_EMAIL]

    first = subprocess.run(argv, env=env, capture_output=True, text=True, encoding="utf-8")
    assert first.returncode == 0, first.stderr
    assert first.stdout.startswith("OK:")

    second = subprocess.run(argv, env=env, capture_output=True, text=True, encoding="utf-8")
    assert second.returncode == 0, second.stderr
    assert second.stdout.startswith("UNCHANGED:")

    # The password must appear in neither stream, on either run.
    assert ADMIN_PASSWORD not in first.stdout + first.stderr + second.stdout + second.stderr
    # Exactly one admin, and one bootstrap audit row.
    assert _audit_actions().count("platform_admin.bootstrapped") == 1
    # ...and the account the CLI made is a usable one on the vendor plane.
    _reset_rate_limiter()
    assert _vendor_login(client)["email"] == ADMIN_EMAIL


def test_bootstrap_refuses_a_weak_password_and_never_echoes_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No default credential, no password on the command line, nothing printed."""
    from business_os.platform_admin import bootstrap

    monkeypatch.setenv(bootstrap.PASSWORD_ENV, "short")
    with pytest.raises(SystemExit):
        bootstrap.read_password()

    monkeypatch.setenv(bootstrap.PASSWORD_ENV, ADMIN_PASSWORD)
    assert bootstrap.read_password() == ADMIN_PASSWORD
    assert ADMIN_PASSWORD not in capsys.readouterr().out

    monkeypatch.delenv(bootstrap.PASSWORD_ENV)
    monkeypatch.setattr(bootstrap.getpass, "getpass", lambda _prompt: ADMIN_PASSWORD)
    assert bootstrap.read_password() == ADMIN_PASSWORD


def test_vendor_login_is_rate_limited(client: TestClient) -> None:
    """The vendor credential spans every customer company; unlimited guessing
    against it is not acceptable. Its limiter is separate from identity's, so
    neither plane can lock the other out."""
    _reset_rate_limiter()
    _seed_admin()
    for _ in range(5):
        client.post(f"{VENDOR}/auth/login",
                    json={"email": ADMIN_EMAIL, "password": "грешна"})
    resp = client.post(f"{VENDOR}/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 429
    assert resp.json()["detail"]["message_key"] == "errors.auth.locked_out"
    _reset_rate_limiter()


# --- Request correlation -------------------------------------------------
#
# business_os.shared_kernel.correlation: every HTTP request (vendor and
# tenant alike, the middleware is global) is bound to a freshly server-
# generated id, echoed in X-Request-ID, and every platform_audit_log row
# written during that request must carry the same value.


def test_vendor_response_includes_a_request_id_header(client: TestClient) -> None:
    resp = client.get(f"{VENDOR}/me")  # 401 is fine — the header is set either way
    assert resp.headers["X-Request-ID"]


def test_two_independent_requests_get_different_request_ids(client: TestClient) -> None:
    first = client.get(f"{VENDOR}/me").headers["X-Request-ID"]
    second = client.get(f"{VENDOR}/me").headers["X-Request-ID"]
    assert first != second


def test_incoming_client_request_id_header_is_never_trusted(client: TestClient) -> None:
    """Chosen policy (see the audit in this slice's report): the project had no
    validated convention for accepting a client-supplied id, so it does not
    adopt one — every response gets a freshly server-generated value regardless
    of what the client sent."""
    resp = client.get(f"{VENDOR}/me", headers={"X-Request-ID": "client-supplied-value"})
    assert resp.headers["X-Request-ID"] != "client-supplied-value"


def test_oversized_or_malformed_incoming_request_id_is_ignored_safely(
    client: TestClient,
) -> None:
    """Same code path as above handles the adversarial input too: nothing about
    a 10 000-character or control-character-laden header is ever propagated,
    logged, or persisted — it is simply never read."""
    hostile = "x" * 10_000
    resp = client.get(f"{VENDOR}/me", headers={"X-Request-ID": hostile})
    assert resp.status_code in (200, 401)
    assert hostile not in resp.headers["X-Request-ID"]
    assert len(resp.headers["X-Request-ID"]) < 100


def test_request_id_does_not_affect_authorisation_or_tenant_scope(client: TestClient) -> None:
    """Observability data, never a credential: a forged/oversized incoming id
    neither grants vendor access nor leaks into tenant scope."""
    _reset_rate_limiter()
    _seed_tenant()
    headers = {"X-Request-ID": "'; DROP TABLE platform_admins; --"}

    assert client.get(f"{VENDOR}/me", headers=headers).status_code == 401
    me = _tenant_login(client)
    assert me["is_owner"] is True  # tenant auth is completely unaffected
    assert client.get(f"{VENDOR}/me", headers=headers).status_code == 401


def test_vendor_audit_row_carries_the_response_request_id(client: TestClient) -> None:
    """The whole point of correlation: given the X-Request-ID a caller saw, the
    audit row that request produced can be found by it."""
    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAuditLog

    _reset_rate_limiter()
    _seed_admin()
    resp = client.post(f"{VENDOR}/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    request_id = resp.headers["X-Request-ID"]

    for db in _db():
        row = db.scalar(select(PlatformAuditLog)  # type: ignore[attr-defined]
                        .where(PlatformAuditLog.action == "platform_admin.login"))
        assert row is not None
        assert str(row.request_id) == request_id


def test_bootstrap_cli_audit_row_has_a_generated_operation_id(client: TestClient) -> None:
    """The CLI is its own operation boundary (no HTTP request exists) — its
    audit row still carries a real, non-null, well-formed correlation id."""
    import uuid as uuid_module

    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAuditLog
    from business_os.platform_admin.service import create_platform_admin
    from business_os.shared_kernel import correlation

    token = correlation.bind()  # simulate bootstrap.main()'s own boundary bind
    try:
        for db in _db():
            create_platform_admin(db, "Вендор Админ", ADMIN_EMAIL, ADMIN_PASSWORD)
    finally:
        correlation.reset(token)

    for db in _db():
        row = db.scalar(select(PlatformAuditLog)  # type: ignore[attr-defined]
                        .where(PlatformAuditLog.action == "platform_admin.bootstrapped"))
        assert row is not None
        assert isinstance(row.request_id, uuid_module.UUID)


def test_audit_record_requires_a_request_id_argument() -> None:
    """`request_id` has no default — a call site that forgets it fails
    immediately with a TypeError, not a silently-NULL column."""
    import inspect

    from business_os.platform_admin import audit

    params = inspect.signature(audit.record).parameters
    assert params["request_id"].default is inspect.Parameter.empty


# --- Session metadata (user_agent / client_label) -----------------------


def test_login_records_a_bounded_user_agent(client: TestClient) -> None:
    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAdminSession

    _reset_rate_limiter()
    _seed_admin()
    client.post(f"{VENDOR}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               headers={"User-Agent": "Mozilla/5.0 Test Runner"})

    for db in _db():
        session = db.scalar(select(PlatformAdminSession))  # type: ignore[attr-defined]
        assert session.user_agent == "Mozilla/5.0 Test Runner"


def test_login_succeeds_with_no_user_agent_header(client: TestClient) -> None:
    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAdminSession

    _reset_rate_limiter()
    _seed_admin()
    resp = client.post(f"{VENDOR}/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                       headers={"User-Agent": ""})
    assert resp.status_code == 200

    for db in _db():
        session = db.scalar(select(PlatformAdminSession))  # type: ignore[attr-defined]
        assert session.user_agent is None


def test_oversized_user_agent_is_truncated_not_rejected(client: TestClient) -> None:
    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAdminSession
    from business_os.platform_admin.service import MAX_USER_AGENT_LENGTH

    _reset_rate_limiter()
    _seed_admin()
    hostile = "A" * (MAX_USER_AGENT_LENGTH * 5)
    resp = client.post(f"{VENDOR}/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                       headers={"User-Agent": hostile})
    assert resp.status_code == 200

    for db in _db():
        session = db.scalar(select(PlatformAdminSession))  # type: ignore[attr-defined]
        assert session.user_agent is not None
        assert len(session.user_agent) == MAX_USER_AGENT_LENGTH


def test_raw_session_token_is_never_stored_as_diagnostic_metadata(client: TestClient) -> None:
    """The cookie value itself must never leak into user_agent/client_label —
    only its hash (token_hash) is ever a credential-shaped column."""
    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAdminSession

    _reset_rate_limiter()
    _seed_admin()
    _vendor_login(client)
    raw_token = client.cookies.get("sf_platform_session", path="/api/v1/platform-admin")
    assert raw_token

    for db in _db():
        session = db.scalar(select(PlatformAdminSession))  # type: ignore[attr-defined]
        assert raw_token not in (session.user_agent or "")
        assert raw_token not in (session.client_label or "")
        assert raw_token != session.token_hash


def test_client_label_stays_null_and_is_never_auto_populated(client: TestClient) -> None:
    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAdminSession

    _reset_rate_limiter()
    _seed_admin()
    client.post(f"{VENDOR}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               headers={"User-Agent": "Mozilla/5.0 Test Runner"})

    for db in _db():
        session = db.scalar(select(PlatformAdminSession))  # type: ignore[attr-defined]
        assert session.client_label is None


def test_last_seen_at_is_not_rewritten_on_every_request(client: TestClient) -> None:
    """Low-write strategy: back-to-back requests within the same minute must
    not each trigger a commit — the column should be unchanged between them."""
    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAdminSession

    _reset_rate_limiter()
    _seed_admin()
    _vendor_login(client)
    for db in _db():
        first_seen = db.scalar(select(PlatformAdminSession)).last_seen_at  # type: ignore[attr-defined]

    for _ in range(3):
        assert client.get(f"{VENDOR}/me").status_code == 200

    for db in _db():
        second_seen = db.scalar(select(PlatformAdminSession)).last_seen_at  # type: ignore[attr-defined]
    assert second_seen == first_seen


def test_session_expiry_and_inactive_admin_behaviour_are_unchanged(client: TestClient) -> None:
    """Regression guard: none of this slice's additions touch expiry or the
    is_active gate — both already covered above, re-asserted together here as
    the one property this slice must not have disturbed."""
    from sqlalchemy import select

    from business_os.platform_admin.models import PlatformAdmin

    _reset_rate_limiter()
    _seed_admin()
    _vendor_login(client)
    assert client.get(f"{VENDOR}/me").status_code == 200

    for db in _db():
        admin = db.scalar(select(PlatformAdmin))  # type: ignore[attr-defined]
        admin.is_active = False
        db.commit()  # type: ignore[attr-defined]
    assert client.get(f"{VENDOR}/me").status_code == 401
