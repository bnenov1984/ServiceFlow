"""In-process domain events (ADR-011): synchronous dispatch, same transaction.

Publishers add the event; subscribers (timeline today; search/notifications later)
write within the caller's session so history can never diverge from state.
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
    order_id: uuid.UUID | None = None
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
