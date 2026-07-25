"""Unit tests for the shared in-process event bus (business_os.shared_kernel.events).

No DB needed: DomainEvent is a plain, non-persisted dataclass and dispatch is
synchronous Python function calls. Covers generic construction with the
neutral `subject_id` field (ADR-BOS-007) and publish/subscribe dispatch
mechanics, independent of any one module's producers/consumers.
"""

import uuid
from collections.abc import Iterator

import pytest

from business_os.shared_kernel import events as events_module
from business_os.shared_kernel.events import DomainEvent, publish, subscribe


@pytest.fixture(autouse=True)
def _isolated_subscribers() -> Iterator[None]:
    """`_subscribers` is a process-global list — real subscribers (e.g.
    serviceflow.timeline's) register on it once, the first time their module
    is imported anywhere in the test session, and stay registered for the
    rest of the process. Swapping in a fresh list for the duration of each
    test (and restoring the original afterwards) isolates these tests
    without permanently wiping out subscribers other test files rely on —
    an earlier version of this fixture cleared the list and never restored
    it, which silently broke every timeline-writing test that happened to
    run later in the same session (found via real Postgres integration
    testing, not by mypy or collection)."""
    original = events_module._subscribers
    events_module._subscribers = []
    try:
        yield
    finally:
        events_module._subscribers = original


def test_domain_event_uses_neutral_subject_id() -> None:
    company_id = uuid.uuid4()
    subject_id = uuid.uuid4()

    event = DomainEvent(
        type="something_happened", company_id=company_id,
        actor_user_id=None, subject_id=subject_id,
    )

    assert event.subject_id == subject_id
    assert not hasattr(event, "order_id")


def test_domain_event_subject_id_is_optional() -> None:
    event = DomainEvent(type="tenant_only_event", company_id=uuid.uuid4(), actor_user_id=None)
    assert event.subject_id is None
    assert event.data == {}


def test_publish_dispatches_to_all_subscribers() -> None:
    received: list[DomainEvent] = []

    @subscribe
    def _collect(_db: object, event: DomainEvent) -> None:
        received.append(event)

    event = DomainEvent(
        type="widget_created", company_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(), subject_id=uuid.uuid4(), data={"k": "v"},
    )
    publish(None, event)  # type: ignore[arg-type]

    assert received == [event]


def test_publish_with_no_subscribers_is_a_noop() -> None:
    event = DomainEvent(type="nobody_listening", company_id=uuid.uuid4(), actor_user_id=None)
    publish(None, event)  # type: ignore[arg-type]  # must not raise


def test_subscribe_does_not_register_the_same_function_twice() -> None:
    def _fn(_db: object, _event: DomainEvent) -> None:
        pass

    subscribe(_fn)
    subscribe(_fn)

    assert events_module._subscribers.count(_fn) == 1
