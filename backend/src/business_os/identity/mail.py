"""Minimal outbound email — one function, stdlib `smtplib` only. Not a
notification service: no queue, no retry, no template engine, no
preferences, no generic event bus. The only current caller is Tenant
Forgot Password V1 (`identity/router.py`'s `forgot_password` endpoint,
`build_reset_link`/`send_password_reset_email` below); if a second real
need for outbound email ever appears, that is the moment to reconsider
this shape, not before.

Lives in `identity`, not `shared_kernel`: it needs `serviceflow.config`
for SMTP settings, and `shared_kernel` is explicitly forbidden from
importing that (`.importlinter`'s `shared-kernel-bottom` contract) —
`identity` already imports it directly elsewhere (`identity/deps.py`),
so this is the same, already-accepted layering, not a new exception.
"""

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from serviceflow.config import get_settings

logger = logging.getLogger(__name__)


def build_reset_link(raw_token: str) -> str:
    """`<public_frontend_url>/reset-password?token=<url-encoded-token>` —
    the one place this URL shape is assembled, so the frontend route and
    the email body can never drift apart."""
    settings = get_settings()
    base = settings.public_frontend_url.rstrip("/")
    return f"{base}/reset-password?token={quote(raw_token, safe='')}"


def send_email(to: str, subject: str, body: str) -> bool:
    """Sends one plain-text email via the configured SMTP relay. Returns
    True on success, False if SMTP isn't configured or delivery failed —
    never raises. Callers (forgot_password) must treat both outcomes the
    same way toward the HTTP caller: the public response stays generic
    either way, this function's job is only server-side logging."""
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        logger.warning("identity.mail: SMTP not configured — message not sent")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError):
        # Never account-existence-revealing, never raised to the caller —
        # a mail-provider outage must never turn an otherwise-successful
        # forgot-password request into a 500 (identity/router.py's
        # forgot_password already committed the token before this runs).
        logger.exception("identity.mail: delivery failed")
        return False
    return True


def send_password_reset_email(to: str, raw_token: str) -> bool:
    """Builds the Bulgarian reset email for Tenant Forgot Password V1 and
    sends it. No current/other account data in the body — only the link
    and its expiry, matching the reset token's own 30-minute TTL
    (identity.service.RESET_TOKEN_TTL)."""
    link = build_reset_link(raw_token)
    subject = "Възстановяване на паролата"
    body = (
        "Получихме заявка за възстановяване на паролата за вашия акаунт.\n\n"
        f"За да зададете нова парола, отворете тази връзка:\n{link}\n\n"
        "Връзката е валидна 30 минути.\n\n"
        "Ако не сте заявили това, можете спокойно да игнорирате този имейл."
    )
    return send_email(to, subject, body)
