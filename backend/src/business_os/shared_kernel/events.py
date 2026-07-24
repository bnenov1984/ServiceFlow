"""In-process domain events (ADR-011): synchronous dispatch, same transaction.

Publishers add the event; subscribers (timeline today; search/notifications later)
write within the caller's session so history can never diverge from state.

`subject_id` is a neutral reference to whatever aggregate the event is about
(ADR-BOS-007) — not order-specific, so any module (ServiceFlow's timeline
today; Professional Services' own activity history later) can use the same
bus without importing order vocabulary. No serialization/persistence of
DomainEvent itself exists: it is a plain in-process dataclass, constructed
and dispatched within the publisher's own transaction; subscribers persist
whatever *they* choose to (e.g. TimelineEvent.order_id, a separate,
ServiceFlow-owned, correctly order-named column that is unaffected by this).
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DomainEvent:
    type: str
    company_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    subject_id: uuid.UUID | None = None
    data: dict[str, Any] = field(default_factory=dict)


Subscriber = Callable[[Session, DomainEvent], None]
_subscribers: list[Subscriber] = []


def subscribe(fn: Subscriber) -> Subscriber:
    if fn not in _subscribers:
        _subscribers.append(fn)
    return fn


def publish(db: Session, event: DomainEvent) -> None:
    for fn in _subscribers:
        fn(db, event)
