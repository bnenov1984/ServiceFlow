"""Tenant Forgot Password V1 — minimal outbound email adapter
(business_os/identity/mail.py). Pure unit tests: no database, no real SMTP
server (a fake `smtplib.SMTP` stand-in is injected via monkeypatch), so
these run regardless of local Postgres availability."""

from dataclasses import dataclass
from typing import Any

import pytest

from business_os.identity import mail


@dataclass
class _FakeSettings:
    smtp_host: str | None = "smtp.example.bg"
    smtp_port: int = 587
    smtp_username: str | None = "user@example.bg"
    smtp_password: str | None = "смтп-парола"
    smtp_from: str | None = "no-reply@example.bg"
    smtp_use_tls: bool = True
    public_frontend_url: str = "https://app.example.bg"


class _FakeSMTP:
    """Stands in for smtplib.SMTP as a context manager — records every call,
    never opens a real socket."""

    instances: list["_FakeSMTP"] = []

    def __init__(self, host: str, port: int, timeout: int = 10) -> None:
        self.host = host
        self.port = port
        self.started_tls = False
        self.login_call: tuple[str, str] | None = None
        self.sent_messages: list[Any] = []
        _FakeSMTP.instances.append(self)

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_call = (username, password)

    def send_message(self, message: Any) -> None:
        self.sent_messages.append(message)


class _RaisingSMTP(_FakeSMTP):
    def send_message(self, message: Any) -> None:
        import smtplib
        raise smtplib.SMTPConnectError(421, "unreachable")


@pytest.fixture(autouse=True)
def _reset_fake_smtp_instances():
    _FakeSMTP.instances.clear()
    yield
    _FakeSMTP.instances.clear()


# --- Reset link construction -------------------------------------------------


def test_build_reset_link_uses_configured_frontend_url_and_url_encodes_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings(
        public_frontend_url="https://app.example.bg",
    ))
    link = mail.build_reset_link("raw+token/with special=chars")
    assert link.startswith("https://app.example.bg/reset-password?token=")
    assert "raw+token/with special=chars" not in link  # must be encoded
    assert "%2B" in link  # '+'
    assert "%2F" in link  # '/'
    assert "%20" in link  # ' '


def test_build_reset_link_strips_trailing_slash_from_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings(
        public_frontend_url="https://app.example.bg/",
    ))
    link = mail.build_reset_link("abc123")
    assert link == "https://app.example.bg/reset-password?token=abc123"
    assert "//reset-password" not in link


# --- send_email: SMTP configured / not configured ---------------------------


def test_send_email_returns_false_when_smtp_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings(smtp_host=None))
    monkeypatch.setattr(mail.smtplib, "SMTP", _FakeSMTP)
    result = mail.send_email("someone@a.bg", "Тема", "Съдържание")
    assert result is False
    assert _FakeSMTP.instances == []  # never even attempted a connection


def test_send_email_returns_false_when_smtp_from_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings(smtp_from=None))
    monkeypatch.setattr(mail.smtplib, "SMTP", _FakeSMTP)
    result = mail.send_email("someone@a.bg", "Тема", "Съдържание")
    assert result is False
    assert _FakeSMTP.instances == []


def test_send_email_sends_via_configured_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(mail.smtplib, "SMTP", _FakeSMTP)

    result = mail.send_email("someone@a.bg", "Тема", "Съдържание на писмото")

    assert result is True
    assert len(_FakeSMTP.instances) == 1
    smtp = _FakeSMTP.instances[0]
    assert smtp.host == "smtp.example.bg"
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.login_call == ("user@example.bg", "смтп-парола")
    assert len(smtp.sent_messages) == 1
    sent = smtp.sent_messages[0]
    assert sent["To"] == "someone@a.bg"
    assert sent["From"] == "no-reply@example.bg"
    assert sent["Subject"] == "Тема"


def test_send_email_skips_starttls_and_login_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings(
        smtp_use_tls=False, smtp_username=None, smtp_password=None,
    ))
    monkeypatch.setattr(mail.smtplib, "SMTP", _FakeSMTP)

    mail.send_email("someone@a.bg", "Тема", "Тяло")

    smtp = _FakeSMTP.instances[0]
    assert smtp.started_tls is False
    assert smtp.login_call is None


def test_send_email_delivery_failure_returns_false_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(mail.smtplib, "SMTP", _RaisingSMTP)

    result = mail.send_email("someone@a.bg", "Тема", "Тяло")
    assert result is False  # never raises, never surfaces as a 500


# --- send_password_reset_email -----------------------------------------------


def test_send_password_reset_email_body_contains_link_and_expiry_no_other_account_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(mail.smtplib, "SMTP", _FakeSMTP)

    result = mail.send_password_reset_email("someone@a.bg", "the-raw-token-abc")

    assert result is True
    sent = _FakeSMTP.instances[0].sent_messages[0]
    body = sent.get_content()
    assert "https://app.example.bg/reset-password?token=the-raw-token-abc" in body
    assert "30" in body  # mentions the expiry window
    # No credential/account-identifying data beyond the link itself.
    assert "смтп" not in body.lower()
    assert "user@example.bg" not in body


# --- Production vs debug logging (no token in production logs) -------------


def test_delivery_failure_log_never_includes_the_link_or_token(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(mail.smtplib, "SMTP", _RaisingSMTP)

    with caplog.at_level("ERROR", logger="business_os.identity.mail"):
        mail.send_email("someone@a.bg", "Тема", "https://app.example.bg/reset-password?token=SECRET-TOKEN-XYZ")

    all_log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "SECRET-TOKEN-XYZ" not in all_log_text
