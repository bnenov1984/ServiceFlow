"""Pure unit/boundary tests for professional_services.assignments.risk
(PS-13 §3/§6). No DB - `today` is always frozen and passed explicitly."""

from datetime import date

import pytest

from professional_services.assignments.risk import (
    ATTENTION_DAYS,
    URGENT_DAYS,
    deadline_risk,
    is_stale,
)

TODAY = date(2026, 7, 18)


@pytest.mark.parametrize(
    ("deadline_on", "expected"),
    [
        (date(2026, 7, 28), "normal"),      # 10 days left
        (date(2026, 7, 25), "attention"),   # exactly the attention boundary, 7 days
        (date(2026, 7, 21), "urgent"),      # exactly the urgent boundary, 3 days
        (date(2026, 7, 19), "urgent"),      # 1 day left
        (date(2026, 7, 18), "critical"),    # due today, 0 days left
        (date(2026, 7, 17), "breached"),    # 1 day overdue
        (date(2026, 6, 1), "breached"),     # long overdue
    ],
)
def test_deadline_risk_boundaries(deadline_on: date, expected: str) -> None:
    assert deadline_risk(deadline_on, "active", TODAY) == expected


def test_no_deadline_is_none() -> None:
    assert deadline_risk(None, "active", TODAY) == "none"


@pytest.mark.parametrize("lifecycle_state", ["delivered", "completed", "cancelled"])
def test_non_active_lifecycle_turns_off_the_risk_stream(lifecycle_state: str) -> None:
    """PS-11 §5: breach warnings stop once the assignment leaves `active`,
    regardless of how overdue the deadline itself looks."""
    assert deadline_risk(date(2026, 1, 1), lifecycle_state, TODAY) == "none"


def test_attention_urgent_ordering_is_consistent() -> None:
    """Sanity check on the module constants themselves, not just the
    hand-picked boundary dates above."""
    assert ATTENTION_DAYS > URGENT_DAYS >= 1


def test_is_stale_true_after_five_business_days() -> None:
    # Friday 2026-07-10 -> Friday 2026-07-17 is exactly 5 business days later
    # (Mon 13, Tue 14, Wed 15, Thu 16, Fri 17), crossing one weekend.
    last_activity = date(2026, 7, 10)
    today = date(2026, 7, 17)
    assert is_stale(last_activity, "active", today) is True


def test_is_stale_false_below_five_business_days() -> None:
    last_activity = date(2026, 7, 13)
    today = date(2026, 7, 17)  # Mon 13 -> Fri 17 is 4 business days
    assert is_stale(last_activity, "active", today) is False


def test_is_stale_ignores_weekends() -> None:
    """A quiet weekend does not, by itself, push an assignment into stale -
    only business days count."""
    last_activity = date(2026, 7, 17)  # Friday
    today = date(2026, 7, 20)  # Monday - one business day later (weekend free)
    assert is_stale(last_activity, "active", today) is False


@pytest.mark.parametrize("lifecycle_state", ["delivered", "completed", "cancelled"])
def test_non_active_assignments_are_never_stale(lifecycle_state: str) -> None:
    assert is_stale(date(2020, 1, 1), lifecycle_state, TODAY) is False


def test_zero_or_negative_span_is_never_stale() -> None:
    assert is_stale(TODAY, "active", TODAY) is False
    assert is_stale(date(2026, 8, 1), "active", TODAY) is False  # "activity" after "today"
