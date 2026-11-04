"""Status model + transition matrix — the frozen docs/02 §1–2 table as code (P0-1).

Kinds drive dashboard/Kanban semantics; display names live in the order_statuses
seed table (renameable per company in Етап 3). The matrix is deliberately code,
not configuration: it is fixed, exhaustively tested, and has no per-company
variation in V1 (docs/08 §What is deliberately absent).
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
    "received": (Kind.WORKING, "Приета", 1),
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
NO = "no"

# The docs/02 §2 matrix, amended by Wave 2 Issue 5 (testing folded into
# repair — no "testing" row/column remains). Rows = from, columns = to.
_M = {
    "received":         {"diagnostics": OK, "waiting_customer": WARN, "waiting_parts": WARN,
                         "repair": WARN, "ready": WARN, "completed": NO,
                         "declined": OK, "unrepairable": OK, "cancelled": OK},
    "diagnostics":      {"received": NO, "waiting_customer": OK, "waiting_parts": OK,
                         "repair": OK, "ready": WARN, "completed": NO,
                         "declined": OK, "unrepairable": OK, "cancelled": OK},
    "waiting_customer": {"received": NO, "diagnostics": OK, "waiting_parts": OK,
                         "repair": OK, "ready": WARN, "completed": NO,
                         "declined": OK, "unrepairable": OK, "cancelled": OK},
    "waiting_parts":    {"received": NO, "diagnostics": OK, "waiting_customer": OK,
                         "repair": OK, "ready": WARN, "completed": NO,
                         "declined": OK, "unrepairable": OK, "cancelled": OK},
    "repair":           {"received": NO, "diagnostics": OK, "waiting_customer": OK,
                         "waiting_parts": OK, "ready": OK, "completed": NO,
                         "declined": NO, "unrepairable": OK, "cancelled": OK},
    "ready":            {"received": NO, "diagnostics": NO, "waiting_customer": NO,
                         "waiting_parts": NO, "repair": OK,
                         "completed": OK, "declined": NO, "unrepairable": NO,
                         "cancelled": OK},
}


def kind_of(code: str) -> Kind:
    return STATUSES[code][0]


def check_transition(from_code: str, to_code: str) -> str:
    """Returns OK / WARN / NO. Terminal sources always NO (BR-2; unlock is separate)."""
    if from_code not in STATUSES or to_code not in STATUSES:
        return NO
    if from_code == to_code or from_code in TERMINAL:
        return NO
    return _M[from_code].get(to_code, NO)


def is_overdue(status_code: str, promised_on: date | None, today: date) -> bool:
    """Per FR-11.1 / discovery 1.2: promised date past, order still active (not
    ready/terminal — ready orders are „done, waiting for pickup", not overdue)."""
    if promised_on is None or promised_on >= today:
        return False
    return status_code in OPEN and kind_of(status_code) != Kind.READY
