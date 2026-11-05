"""Status model + transition matrix — the frozen docs/02 §1–2 table as code (P0-1).

Kinds drive dashboard/Kanban semantics; display names live in the order_statuses
seed table (renameable per company in Етап 3). The matrix is deliberately code,
not configuration: it is fixed, exhaustively tested, and has no per-company
variation in V1 (docs/08 §What is deliberately absent).

order-workflow-revamp WP-G (Q1–Q4, grilling 24.10.2026, AUDIT §7): a full
matrix rewrite — forward moves only in the regular status menu, backward
moves (Чака клиент/Чака части/Ремонт → Диагностика, Готова → Ремонт) split
into their own `_BACKWARD` table and surfaced as a distinct `BACK` verdict,
since they're offered through a separate "Върни към…" action with a
mandatory reason, never the forward dropdown. "cancelled" is deliberately in
neither table — it's reachable from any open status via the existing
Owner-only secondary action (unconditional "ok", same wildcard-escape
precedent as before this WP), not a matrix-governed destination.
"""

from datetime import date
from enum import StrEnum


class Kind(StrEnum):
    WORKING = "working"
    WAITING = "waiting"
    READY = "ready"
    TERMINAL_SUCCESS = "terminal_success"
    TERMINAL_FAILURE = "terminal_failure"


# code -> (kind, default BG name, sort)
# Issue 5 (Wave 2): "testing" removed — it is now considered part of "repair",
# not a separate stage. Migration 0021 reassigns any existing testing orders
# to repair and drops the now-unreferenced order_statuses row; this dict (and
# the matrix below) reflects only the current, active status set — "testing"
# events already recorded on a TimelineEvent are untouched (append-only,
# never rewritten).
#
# Wave 4 audit correction (2026-09-25): "delivered"/"Предадена" renamed to
# "completed"/"Приключена" — the PO's original Wave 4 ask (a distinct
# post-Ready completion step) was implemented by reusing the pre-existing
# terminal-success status instead of adding a new one; the PO reviewed that
# divergence and chose to rename the existing status rather than add a
# second terminal state. Migration 0031 follows the same reassign-then-drop
# pattern as 0021.
STATUSES: dict[str, tuple[Kind, str, int]] = {
    # order-workflow-revamp WP-G (Q1): display-renamed "НОВА" — the code
    # stays `received` (no status-model/migration change, just the label);
    # its screen and transition set are also now distinct (see router.py /
    # OrderHeader.tsx) — only Диагностика (ПРИЕМИ), Отказана (ОТКАЖИ), and
    # Анулирана (Owner-only) are reachable from it.
    "received": (Kind.WORKING, "НОВА", 1),
    "diagnostics": (Kind.WORKING, "Диагностика", 2),
    "waiting_customer": (Kind.WAITING, "Чака клиент", 3),
    "waiting_parts": (Kind.WAITING, "Чака части", 4),
    "repair": (Kind.WORKING, "Ремонт", 5),
    "ready": (Kind.READY, "Готова", 7),
    "completed": (Kind.TERMINAL_SUCCESS, "Приключена", 8),
    "declined": (Kind.TERMINAL_FAILURE, "Отказана", 9),
    "unrepairable": (Kind.TERMINAL_FAILURE, "Неремонтируема", 10),
    "cancelled": (Kind.TERMINAL_FAILURE, "Анулирана", 11),
}

TERMINAL = {c for c, (k, _, _) in STATUSES.items()
            if k in (Kind.TERMINAL_SUCCESS, Kind.TERMINAL_FAILURE)}
OPEN = set(STATUSES) - TERMINAL
# Statuses that count as a technician's current load in the technician picker
# (WP-F, PO decision Q22): actively being worked on, not waiting or ready.
TECHNICIAN_LOAD = {"diagnostics", "repair"}

# order-workflow-revamp WP-I (Q13d): a part/labor line may only be added
# while the order is in one of these statuses — never at intake (reverses
# Issue 29), never on "received"/"ready" or any terminal status.
LINE_CREATION_STATUSES = {"diagnostics", "waiting_customer", "waiting_parts", "repair"}

OK = "ok"
WARN = "warn"  # allowed with a skip warning (docs/02 §2)
BACK = "back"  # allowed only via the dedicated "Върни към…" action, mandatory reason
NO = "no"

# order-workflow-revamp WP-G (Q1–Q4, AUDIT §7, 24.10.2026): forward moves
# only — never a backward target (those live in `_BACKWARD` below), never
# "cancelled" (the open-everywhere Owner-only wildcard, handled separately
# in `check_transition`). "received" only forwards to "diagnostics"
# (ПРИЕМИ); "declined" from "received" (ОТКАЖИ) is its own dedicated button,
# not a dropdown entry, but still a normal forward "ok" cell here — the UI
# choice of button-vs-dropdown doesn't change what the matrix allows.
_FORWARD: dict[str, dict[str, str]] = {
    "received": {"diagnostics": OK, "declined": OK},
    "diagnostics": {"waiting_customer": OK, "waiting_parts": OK, "repair": OK,
                    "ready": WARN, "unrepairable": OK, "declined": OK},
    "waiting_customer": {"waiting_parts": OK, "repair": OK, "ready": WARN, "declined": OK},
    "waiting_parts": {"waiting_customer": OK, "repair": OK, "ready": WARN, "declined": OK},
    "repair": {"waiting_customer": OK, "waiting_parts": OK, "ready": OK},
    "ready": {"completed": OK},
}
# Q3/Q3b: backward moves — allowed, but only via a separate "Върни към…"
# action with a mandatory reason (service.change_status), never offered in
# the regular forward status menu.
_BACKWARD: dict[str, set[str]] = {
    "waiting_customer": {"diagnostics"},
    "waiting_parts": {"diagnostics"},
    "repair": {"diagnostics"},
    "ready": {"repair"},
}


def kind_of(code: str) -> Kind:
    return STATUSES[code][0]


def check_transition(from_code: str, to_code: str) -> str:
    """Returns OK / WARN / BACK / NO. Terminal sources always NO (BR-2; unlock
    is separate). "cancelled" is always OK from any non-terminal, non-self
    source — reachable from every open status via the Owner-only secondary
    action (service.change_status enforces the Owner/reason gate; this
    matrix only ever says whether the *code* allows it at all)."""
    if from_code not in STATUSES or to_code not in STATUSES:
        return NO
    if from_code == to_code or from_code in TERMINAL:
        return NO
    if to_code == "cancelled":
        return OK
    if to_code in _BACKWARD.get(from_code, ()):
        return BACK
    return _FORWARD.get(from_code, {}).get(to_code, NO)


def is_overdue(status_code: str, promised_on: date | None, today: date) -> bool:
    """Per FR-11.1 / discovery 1.2: promised date past, order still active (not
    ready/terminal — ready orders are „done, waiting for pickup", not overdue)."""
    if promised_on is None or promised_on >= today:
        return False
    return status_code in OPEN and kind_of(status_code) != Kind.READY
