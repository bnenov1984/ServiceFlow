"""Pure unit tests for professional_services.actions.service.compute_risk —
no DB needed. Request-time computation, no persisted risk column, no job."""

from datetime import date, timedelta

from professional_services.actions.service import ATTENTION_WINDOW, compute_risk

TODAY = date(2026, 7, 19)


def test_completed_is_always_done() -> None:
    assert compute_risk(TODAY - timedelta(days=5), completed=True, today=TODAY) == "done"
    assert compute_risk(TODAY + timedelta(days=5), completed=True, today=TODAY) == "done"


def test_past_due_is_overdue() -> None:
    assert compute_risk(TODAY - timedelta(days=1), completed=False, today=TODAY) == "overdue"


def test_due_today_is_attention() -> None:
    assert compute_risk(TODAY, completed=False, today=TODAY) == "attention"


def test_within_attention_window_is_attention() -> None:
    edge = TODAY + ATTENTION_WINDOW
    assert compute_risk(edge, completed=False, today=TODAY) == "attention"


def test_beyond_attention_window_is_ok() -> None:
    beyond = TODAY + ATTENTION_WINDOW + timedelta(days=1)
    assert compute_risk(beyond, completed=False, today=TODAY) == "ok"
