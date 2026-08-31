"""P0-1: the transition matrix, exhaustively — every cell of docs/02 §2, as code.

Pure unit tests, no DB. The table below is transcribed verbatim from the frozen
document so a diff against docs/02 §2 is a diff against this file.

Wave 2 Issue 5 amendment: "testing" is no longer an active status (folded
into "repair") — the row/column is gone from EXPECTED below, matching
statuses.py exactly.
"""

from serviceflow.service_orders import statuses

ALL = list(statuses.STATUSES)

# from -> {to: verdict}, exactly as docs/02 §2 (blank cells collapse to "no",
# self-transitions and "from terminal" always "no" regardless of the table).
EXPECTED: dict[str, dict[str, str]] = {
    "received": {
        "diagnostics": "ok", "waiting_customer": "warn", "waiting_parts": "warn",
        "repair": "warn", "ready": "warn", "delivered": "no",
        "declined": "ok", "unrepairable": "ok", "cancelled": "ok",
    },
    "diagnostics": {
        "received": "no", "waiting_customer": "ok", "waiting_parts": "ok",
        "repair": "ok", "ready": "warn", "delivered": "no",
        "declined": "ok", "unrepairable": "ok", "cancelled": "ok",
    },
    "waiting_customer": {
        "received": "no", "diagnostics": "ok", "waiting_parts": "ok",
        "repair": "ok", "ready": "warn", "delivered": "no",
        "declined": "ok", "unrepairable": "ok", "cancelled": "ok",
    },
    "waiting_parts": {
        "received": "no", "diagnostics": "ok", "waiting_customer": "ok",
        "repair": "ok", "ready": "warn", "delivered": "no",
        "declined": "ok", "unrepairable": "ok", "cancelled": "ok",
    },
    "repair": {
        "received": "no", "diagnostics": "ok", "waiting_customer": "ok",
        "waiting_parts": "ok", "ready": "ok", "delivered": "no",
        "declined": "no", "unrepairable": "ok", "cancelled": "ok",
    },
    "ready": {
        "received": "no", "diagnostics": "no", "waiting_customer": "no",
        "waiting_parts": "no", "repair": "ok", "delivered": "ok",
        "declined": "no", "unrepairable": "no", "cancelled": "ok",
    },
}

TERMINAL_CODES = {"delivered", "declined", "unrepairable", "cancelled"}


def test_expected_table_covers_every_open_status_pair() -> None:
    # Guard the fixture itself: every open "from" x every "to" != itself is listed.
    for frm in EXPECTED:
        assert frm not in TERMINAL_CODES
        others = set(ALL) - {frm}
        assert set(EXPECTED[frm]) == others, frm


def test_matrix_matches_frozen_docs_table() -> None:
    for frm, row in EXPECTED.items():
        for to, verdict in row.items():
            assert statuses.check_transition(frm, to) == verdict, f"{frm} -> {to}"


def test_terminal_statuses_accept_no_further_transitions() -> None:
    for frm in TERMINAL_CODES:
        for to in ALL:
            assert statuses.check_transition(frm, to) == statuses.NO, f"{frm} -> {to}"


def test_self_transition_always_no() -> None:
    for code in ALL:
        assert statuses.check_transition(code, code) == statuses.NO


def test_unknown_codes_are_no() -> None:
    assert statuses.check_transition("received", "not_a_status") == statuses.NO
    assert statuses.check_transition("not_a_status", "received") == statuses.NO


def test_kind_partition() -> None:
    assert statuses.TERMINAL == TERMINAL_CODES
    assert set(ALL) - TERMINAL_CODES == statuses.OPEN
    assert statuses.kind_of("ready") == statuses.Kind.READY
    assert statuses.kind_of("delivered") == statuses.Kind.TERMINAL_SUCCESS
