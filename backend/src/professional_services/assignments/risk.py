"""Deterministic deadline-risk and staleness engine (PS-13). Pure functions
only - no DB, no HTTP, no clock reads (`today` is always an explicit
parameter, so tests can freeze it and the same inputs always produce the
same output, per INV-9 in the module's own frozen docs).

Thresholds are hardcoded module constants, not per-organisation settings -
configurable thresholds/service types are explicitly out of scope for this
slice (they need org settings storage this slice does not build). Staleness
uses simple Monday-Friday business-day counting with no holiday calendar
(PS-13's documented holiday table is a separate, later concern); this is
still fully deterministic, just coarser than the eventual design.
"""

from datetime import date, timedelta

DeadlineRisk = str  # "none" | "normal" | "attention" | "urgent" | "critical" | "breached"

ATTENTION_DAYS = 7
URGENT_DAYS = 3
STALE_BUSINESS_DAYS = 5

# Lifecycle states for which the deadline-risk stream is live (PS-11 §5:
# delivered/completed/cancelled all turn it off - the outcome already
# happened or was abandoned, a breach warning past that point is noise).
_RISK_LIVE_STATES = frozenset({"active"})


def deadline_risk(deadline_on: date | None, lifecycle_state: str, today: date) -> DeadlineRisk:
    """PS-13 §3. `none` when there is nothing to warn about (no deadline
    entered, or the assignment already left the active lifecycle state)."""
    if lifecycle_state not in _RISK_LIVE_STATES or deadline_on is None:
        return "none"
    days_left = (deadline_on - today).days
    if days_left > ATTENTION_DAYS:
        return "normal"
    if days_left > URGENT_DAYS:
        return "attention"
    if days_left > 0:
        return "urgent"
    if days_left == 0:
        return "critical"
    return "breached"


def _business_days_between(start: date, end: date) -> int:
    """Count Monday-Friday days strictly between `start` and `end` (end
    exclusive of start). Negative or zero span (end <= start) -> 0."""
    if end <= start:
        return 0
    count = 0
    day = start + timedelta(days=1)
    while day <= end:
        if day.weekday() < 5:  # Mon=0 .. Fri=4
            count += 1
        day += timedelta(days=1)
    return count


def is_stale(last_activity_on: date, lifecycle_state: str, today: date) -> bool:
    """PS-13 §6 I-1, business-day span (Monday-Friday, no holidays this
    slice). Only meaningful for active assignments - delivered/completed/
    cancelled assignments are not "going stale", they are simply done."""
    if lifecycle_state not in _RISK_LIVE_STATES:
        return False
    return _business_days_between(last_activity_on, today) >= STALE_BUSINESS_DAYS
