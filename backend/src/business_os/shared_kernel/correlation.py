"""Request/operation correlation id: a context-propagated value that ties an
application log line to the platform audit row it produced, and both to the
`X-Request-ID` an operator sees in the response.

This is observability data, never a security credential: it is never checked
for authorisation and never trusted as globally unique merely because a caller
supplied it (see `bind()`).

Lives in shared_kernel — genuinely neutral, like `passwords.py` — because both
the tenant application and the Vendor Control Plane need it and neither may
import the other.
"""

import logging
import uuid
from contextvars import ContextVar, Token

REQUEST_ID_HEADER = "X-Request-ID"

_current: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def new_id() -> str:
    """A fresh correlation value. Deliberately plain `uuid4`, not
    `shared_kernel.ids.new_id` (UUIDv7) — that function identifies a *row*
    (ADR-013); a correlation id identifies a request or CLI run and owns no
    row of its own, so there is no ordering property worth paying for."""
    return str(uuid.uuid4())


def bind(value: str | None = None) -> Token[str | None]:
    """Claim the current context (an HTTP request, a CLI invocation) with a
    correlation id, generating one if none is given. Call once at the real
    operation boundary — the HTTP middleware, or a CLI's own `main()` — and
    `reset()` the returned token when that operation ends."""
    return _current.set(value or new_id())


def reset(token: Token[str | None]) -> None:
    _current.reset(token)


def current() -> str | None:
    return _current.get()


def ensure_bound() -> str:
    """The id for the current context, binding a fresh one if nothing has
    claimed this context yet.

    Prefer binding explicitly at the real boundary (HTTP middleware, CLI
    `main()`) — this exists so a service function that writes an audit row
    (`platform_admin.service.login`/`logout`/`create_platform_admin`) always
    has a non-null id to hand `audit.record()`, including when called
    directly (a script, a test) with no boundary above it, without every such
    call site having to invent one by hand.
    """
    existing = current()
    if existing is not None:
        return existing
    value = new_id()
    bind(value)
    return value


class CorrelationLogFilter(logging.Filter):
    """Attaches the bound correlation id to every log record that doesn't
    already carry one, so `KeyValueFormatter` (serviceflow.logging_setup) can
    print it. Installed once, on the root handler, in `setup_logging()`."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            record.request_id = current()
        return True
