"""Tenant Forgot Password / Password Reset V1 (identity.service.
request_password_reset()/reset_password()): opaque single-use DB-hashed
token, 30-minute TTL, anti-enumeration, independent per-IP/per-email rate
limits, all-sessions revocation on success. Vendor/PlatformAdmin reset is
explicitly out of scope — untouched by any of this."""

import os
import threading

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)

EMAIL = "maria@a.bg"
PASSWORD = "парола-оригинал-123"


def _seed(email: str = EMAIL, password: str = PASSWORD,
         company: str = "Сервиз А") -> None:
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        seed_company(db, company, "Мария", email, password)


def _clear_limiter() -> None:
    from business_os.identity import service
    service._failures.clear()  # noqa: SLF001


def _forgot(client: TestClient, email: str = EMAIL) -> "object":
    return client.post("/api/v1/auth/forgot-password", json={"email": email})


def _reset(client: TestClient, token: str, password: str = "нова-парола-456") -> "object":
    return client.post("/api/v1/auth/reset-password", json={"token": token, "password": password})


def _latest_token_row(email: str = EMAIL) -> object:
    from sqlalchemy import select

    from business_os.identity.models import PasswordResetToken, User
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        row = db.scalar(
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id)
            .order_by(PasswordResetToken.created_at.desc())
        )
        assert row is not None
        return row
    raise AssertionError("unreachable")


def _all_token_rows(email: str = EMAIL) -> list[object]:
    from sqlalchemy import select

    from business_os.identity.models import PasswordResetToken, User
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        return list(db.scalars(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        ))
    raise AssertionError("unreachable")


def _raw_token_for(email: str = EMAIL, client_key: str = "test-client") -> str:
    """Bypasses HTTP/email delivery (Batch A has none yet) to obtain the raw
    token directly from the service layer — the only way a test can drive
    the reset-submit flow before Batch B's mailer exists."""
    from sqlalchemy import select

    from business_os.identity import service
    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        raw = service.request_password_reset(db, email, client_key)
        assert raw is not None
        return raw
    raise AssertionError("unreachable")


def _set_user_active(email: str, active: bool) -> None:
    from sqlalchemy import select

    from business_os.identity.models import User
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        user.is_active = active
        db.commit()


def _archive_company(email: str) -> None:
    from sqlalchemy import select

    from business_os.identity.models import Company, User
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        company = db.get(Company, user.company_id)
        assert company is not None
        from datetime import UTC, datetime
        company.archived_at = datetime.now(UTC)
        db.commit()


def _audit_events(email: str, action: str) -> list[object]:
    from sqlalchemy import select

    from business_os.identity.models import AuditLog, User
    from business_os.shared_kernel.db import open_session

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        return list(db.scalars(
            select(AuditLog).where(AuditLog.user_id == user.id, AuditLog.action == action)
        ))
    raise AssertionError("unreachable")


@pytest.fixture(autouse=True)
def _reset_limiter():
    _clear_limiter()
    yield
    _clear_limiter()


# --- Request: happy path / token creation -----------------------------------


def test_active_user_request_creates_one_valid_hashed_token(client: TestClient) -> None:
    _seed()
    resp = _forgot(client)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    rows = _all_token_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row.used_at is None
    assert row.token_hash != ""
    # The hash is a sha256 hex digest, not the raw urlsafe token shape.
    assert len(row.token_hash) == 64
    int(row.token_hash, 16)  # raises if not valid hex


def test_raw_token_is_not_persisted(client: TestClient) -> None:
    from business_os.identity import security

    _seed()
    raw = _raw_token_for()
    row = _latest_token_row()
    assert row.token_hash == security.hash_token(raw)
    assert raw not in row.token_hash


def test_token_expiry_is_thirty_minutes(client: TestClient) -> None:
    from datetime import UTC

    _seed()
    _forgot(client)
    row = _latest_token_row()
    delta = row.expires_at.replace(tzinfo=UTC) - row.created_at.replace(tzinfo=UTC)
    assert 29 <= delta.total_seconds() / 60 <= 31


def test_new_request_invalidates_prior_unused_token(client: TestClient) -> None:
    _seed()
    first_raw = _raw_token_for()
    second_raw = _raw_token_for()
    assert first_raw != second_raw

    rows = _all_token_rows()
    assert len(rows) == 2
    first_row = next(r for r in rows if r.token_hash != _latest_token_row().token_hash)
    assert first_row.used_at is not None  # invalidated by the second request

    # The first (invalidated) token must now be rejected on submit.
    resp = _reset(client, first_raw)
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.auth.reset_token_invalid"


# --- Anti-enumeration: identical response, no usable token -----------------


def test_unknown_email_returns_identical_response_and_creates_no_token(client: TestClient) -> None:
    _seed()
    known = _forgot(client, EMAIL)
    unknown = _forgot(client, "nobody@nowhere.bg")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"ok": True}


def test_inactive_user_returns_identical_response_and_creates_no_token(
    client: TestClient,
) -> None:
    _seed()
    _set_user_active(EMAIL, False)
    resp = _forgot(client)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert _all_token_rows() == []


def test_archived_company_returns_identical_response_and_creates_no_token(
    client: TestClient,
) -> None:
    _seed()
    _archive_company(EMAIL)
    resp = _forgot(client)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert _all_token_rows() == []


# --- Submit: validation / rejection cases -----------------------------------


def test_expired_token_rejected(client: TestClient) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from business_os.identity.models import PasswordResetToken
    from business_os.shared_kernel.db import open_session

    _seed()
    raw = _raw_token_for()

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        row = db.scalar(select(PasswordResetToken))
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

    resp = _reset(client, raw)
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.auth.reset_token_invalid"


def test_used_token_rejected(client: TestClient) -> None:
    _seed()
    raw = _raw_token_for()
    assert _reset(client, raw).status_code == 200

    resp = _reset(client, raw, password="друга-нова-парола-789")
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.auth.reset_token_invalid"


def test_second_use_of_token_rejected(client: TestClient) -> None:
    _seed()
    raw = _raw_token_for()
    first = _reset(client, raw)
    second = _reset(client, raw)
    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"]["message_key"] == "errors.auth.reset_token_invalid"


def test_random_token_rejected(client: TestClient) -> None:
    _seed()
    resp = _reset(client, "not-a-real-token-at-all")
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.auth.reset_token_invalid"


def test_reset_refuses_user_that_became_inactive_after_request(client: TestClient) -> None:
    _seed()
    raw = _raw_token_for()
    _set_user_active(EMAIL, False)

    resp = _reset(client, raw)
    assert resp.status_code == 400
    assert resp.json()["detail"]["message_key"] == "errors.auth.reset_token_invalid"


def test_password_policy_min_length_enforced(client: TestClient) -> None:
    _seed()
    raw = _raw_token_for()
    resp = _reset(client, raw, password="short12345")
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


def test_password_policy_max_length_enforced(client: TestClient) -> None:
    _seed()
    raw = _raw_token_for()
    resp = _reset(client, raw, password="a" * 201)
    assert resp.status_code == 400
    assert resp.json()["message_key"] == "errors.validation"


# --- Successful reset effects -----------------------------------------------


def test_successful_reset_changes_password_and_old_password_stops_working(
    client: TestClient,
) -> None:
    _seed()
    raw = _raw_token_for()
    resp = _reset(client, raw, password="нова-истинска-парола-999")
    assert resp.status_code == 200

    old_login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert old_login.status_code == 401

    new_login = client.post("/api/v1/auth/login",
                            json={"email": EMAIL, "password": "нова-истинска-парола-999"})
    assert new_login.status_code == 200


def test_successful_reset_revokes_all_existing_sessions(client: TestClient) -> None:
    from sqlalchemy import select

    from business_os.identity.models import AuthSession, User
    from business_os.shared_kernel.db import open_session

    _seed()
    me = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    assert me["email"] == EMAIL  # sanity: the login above did succeed
    stale_cookie = client.cookies.get("sf_session")
    assert stale_cookie
    assert client.get("/api/v1/auth/me").status_code == 200  # session is live pre-reset

    raw = _raw_token_for()
    assert _reset(client, raw, password="нова-парола-от-нулиране-000").status_code == 200

    for db in open_session(os.environ["SERVICEFLOW_DATABASE_URL"]):
        user = db.scalar(select(User).where(User.email == EMAIL))
        assert user is not None
        sessions = list(db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)))
        assert len(sessions) >= 1
        assert all(s.revoked_at is not None for s in sessions)

    # The reset endpoint itself never touches cookies (no Set-Cookie), so the
    # test client still carries the pre-reset session cookie — it must now
    # be rejected as revoked.
    assert client.cookies.get("sf_session") == stale_cookie
    assert client.get("/api/v1/auth/me").status_code == 401


def test_reset_does_not_auto_login(client: TestClient) -> None:
    _seed()
    raw = _raw_token_for()
    resp = _reset(client, raw)
    assert resp.status_code == 200
    assert "sf_session" not in resp.cookies


# --- Concurrency / single-use race safety -----------------------------------


def test_concurrent_reset_submissions_only_one_succeeds(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Thread A is deliberately paused (via a patched `_audit`, called right
    before `reset_password()`'s single commit — same technique
    test_invoice_issue.py's own concurrency tests use with `publish`) after
    it has locked the token row (`with_for_update`) and validated/consumed
    it in memory, but before committing. Thread B, started while A is still
    paused, must genuinely block on that row lock (proven via
    thread.is_alive(), not timing), see the token already `used_at`-set once
    it unblocks, and reject with the same generic invalid-token error."""
    from sqlalchemy.orm import Session, sessionmaker

    from business_os.identity import service as identity_service
    from business_os.shared_kernel.db import get_engine

    _seed()
    raw = _raw_token_for()

    url = os.environ["SERVICEFLOW_DATABASE_URL"]

    def _new_session() -> Session:
        return sessionmaker(bind=get_engine(url), expire_on_commit=False, class_=Session)()

    reached_hold_point = threading.Event()
    release_a = threading.Event()
    real_audit = identity_service._audit  # noqa: SLF001

    def _paused_audit(db: Session, company_id: object, user_id: object,
                      action: str, detail: dict[str, object] | None = None) -> None:
        if action == "password_reset_completed":
            reached_hold_point.set()
            assert release_a.wait(timeout=10), "test never released thread A"
        real_audit(db, company_id, user_id, action, detail)

    monkeypatch.setattr(identity_service, "_audit", _paused_audit)

    results: list[object] = [None, None]

    def run(index: int, password: str, client_key: str) -> None:
        db = _new_session()
        try:
            identity_service.reset_password(db, raw, password, client_key)
            results[index] = "ok"
        except BaseException as exc:  # noqa: BLE001 — captured, asserted below
            results[index] = exc
        finally:
            db.close()

    thread_a = threading.Thread(target=run, args=(0, "паралелна-парола-111", "client-a"))
    thread_a.start()
    assert reached_hold_point.wait(timeout=5), "thread A never reached the pre-commit hold point"

    thread_b = threading.Thread(target=run, args=(1, "паралелна-парола-222", "client-b"))
    thread_b.start()
    thread_b.join(timeout=1)
    assert thread_b.is_alive(), "loser did not block on the contested token row lock"

    release_a.set()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)
    assert not thread_a.is_alive()
    assert not thread_b.is_alive()

    assert results[0] == "ok"
    assert isinstance(results[1], identity_service.AuthError)
    assert results[1].message_key == "errors.auth.reset_token_invalid"


# --- Rate limiting -----------------------------------------------------------


def test_per_email_reset_request_limiter(client: TestClient) -> None:
    _seed()
    for _ in range(3):
        assert _forgot(client).status_code == 200
    resp = _forgot(client)
    assert resp.status_code == 429
    assert resp.json()["detail"]["message_key"] == "errors.auth.locked_out"


def test_per_ip_reset_request_limiter_independent_of_email(client: TestClient) -> None:
    """A single IP requesting reset for many DIFFERENT emails must still hit
    its own cap — proving the per-email limiter alone would not have caught
    this (each individual email is under its own 3-request cap)."""
    _seed("victim1@a.bg", company="Сервиз Б1")
    _seed("victim2@a.bg", company="Сервиз Б2")
    _seed("victim3@a.bg", company="Сервиз Б3")
    emails = ["victim1@a.bg", "victim2@a.bg", "victim3@a.bg",
             "victim4@a.bg", "victim5@a.bg", "victim6@a.bg",
             "victim7@a.bg", "victim8@a.bg", "victim9@a.bg", "victim10@a.bg"]
    for email in emails:
        resp = _forgot(client, email)
        assert resp.status_code == 200, f"unexpected failure for {email}: {resp.text}"
    resp = _forgot(client, "victim11@a.bg")
    assert resp.status_code == 429
    assert resp.json()["detail"]["message_key"] == "errors.auth.locked_out"


def test_reset_submit_limiter_exists(client: TestClient) -> None:
    _seed()
    for _ in range(10):
        resp = _reset(client, "wrong-token-guess")
        assert resp.status_code == 400
    resp = _reset(client, "wrong-token-guess")
    assert resp.status_code == 429
    assert resp.json()["detail"]["message_key"] == "errors.auth.locked_out"


# --- Audit / no raw-token leakage -------------------------------------------


def test_audit_events_never_contain_the_raw_token(client: TestClient) -> None:
    _seed()
    raw = _raw_token_for()
    _reset(client, raw, password="одитна-нова-парола-333")

    requested = _audit_events(EMAIL, "password_reset_requested")
    completed = _audit_events(EMAIL, "password_reset_completed")
    assert len(requested) >= 1
    assert len(completed) == 1
    for event in [*requested, *completed]:
        assert raw not in str(event.detail)


def test_missing_csrf_header_is_not_required_for_public_reset_endpoints(
    client: TestClient,
) -> None:
    """forgot-password/reset-password are public/pre-auth, mirroring
    /auth/login — no X-CSRF-Token is required or even possible to supply
    correctly (there is no session yet to bind one to)."""
    _seed()
    resp = _forgot(client)
    assert resp.status_code == 200  # no CSRF header sent, still succeeds


# --- Batch B: email delivery wiring through the endpoint --------------------
#
# These monkeypatch business_os.identity.mail.send_password_reset_email —
# never a real SMTP server (backend/tests/test_identity_mail.py already
# covers the adapter itself in full isolation).


def test_mail_adapter_invoked_for_a_valid_eligible_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from business_os.identity import mail

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        mail, "send_password_reset_email",
        lambda to, raw_token: calls.append((to, raw_token)) or True,
    )
    _seed()
    resp = _forgot(client)
    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0][0] == EMAIL
    assert calls[0][1]  # a non-empty raw token was passed through


def test_no_mail_sent_for_unknown_email(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from business_os.identity import mail

    calls: list[object] = []
    monkeypatch.setattr(mail, "send_password_reset_email",
                        lambda to, raw_token: calls.append((to, raw_token)) or True)
    _seed()
    resp = _forgot(client, "nobody@nowhere.bg")
    assert resp.status_code == 200
    assert calls == []


def test_no_mail_sent_for_inactive_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from business_os.identity import mail

    calls: list[object] = []
    monkeypatch.setattr(mail, "send_password_reset_email",
                        lambda to, raw_token: calls.append((to, raw_token)) or True)
    _seed()
    _set_user_active(EMAIL, False)
    resp = _forgot(client)
    assert resp.status_code == 200
    assert calls == []


def test_generic_http_response_unchanged_when_delivery_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mail-provider outage must never surface as a distinguishable
    response — same {"ok": True} shape and status code as a fully
    successful request."""
    from business_os.identity import mail

    monkeypatch.setattr(mail, "send_password_reset_email", lambda to, raw_token: False)
    _seed()
    resp = _forgot(client)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_production_logs_do_not_expose_the_reset_token_or_link(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    from business_os.identity import mail

    monkeypatch.setattr(mail, "send_password_reset_email", lambda to, raw_token: True)
    _seed()

    with caplog.at_level("INFO", logger="business_os.identity.router"):
        resp = _forgot(client)
    assert resp.status_code == 200

    row = _latest_token_row()
    all_log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert row.token_hash not in all_log_text
    assert "reset-password?token=" not in all_log_text  # debug is off by default


def test_debug_logs_the_full_reset_link(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    from business_os.identity import mail
    from business_os.identity import router as identity_router
    from serviceflow.config import get_settings

    monkeypatch.setattr(mail, "send_password_reset_email", lambda to, raw_token: True)
    real_settings = get_settings()
    debug_settings = real_settings.model_copy(update={"debug": True})
    monkeypatch.setattr(identity_router, "get_settings", lambda: debug_settings)
    _seed()

    with caplog.at_level("INFO", logger="business_os.identity.router"):
        resp = _forgot(client)
    assert resp.status_code == 200

    all_log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "reset-password?token=" in all_log_text
