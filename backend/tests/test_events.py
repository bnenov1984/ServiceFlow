"""Unit tests for the shared in-process event bus (business_os.shared_kernel.events).

No DB needed: DomainEvent is a plain, non-persisted dataclass and dispatch is
synchronous Python function calls. Covers generic construction with the
neutral `subject_id` field (ADR-BOS-007) and publish/subscribe dispatch
mechanics, independent of any one module's producers/consumers.
"""

import uuid

from business_os.shared_kernel import events as events_module
from business_os.shared_kernel.events import DomainEvent, publish, subscribe


def _isolated_subscribers() -> None:
    """Each test gets a clean subscriber list — the module-level list is
    process-global, so tests must not leak subscribers into each other."""
    events_module._subscribers = []


def test_domain_event_uses_neutral_subject_id() -> None:
    _isolated_subscribers()
    company_id = uuid.uuid4()
    subject_id = uuid.uuid4()

    event = DomainEvent(
        type="something_happened", company_id=company_id,
        actor_user_id=None, subject_id=subject_id,
    )

    assert event.subject_id == subject_id
    assert not hasattr(event, "order_id")


def test_domain_event_subject_id_is_optional() -> None:
    _isolated_subscribers()
    event = DomainEvent(type="tenant_only_event", company_id=uuid.uuid4(), actor_user_id=None)
    assert event.subject_id is None
    assert event.data == {}


def test_publish_dispatches_to_all_subscribers() -> None:
    _isolated_subscribers()
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
    events_module._subscribers.remove(_collect)


def test_publish_with_no_subscribers_is_a_noop() -> None:
    _isolated_subscribers()
    event = DomainEvent(type="nobody_listening", company_id=uuid.uuid4(), actor_user_id=None)
    publish(None, event)  # type: ignore[arg-type]  # must not raise


def test_subscribe_does_not_register_the_same_function_twice() -> None:
    _isolated_subscribers()

    def _fn(_db: object, _event: DomainEvent) -> None:
        pass

    subscribe(_fn)
    subscribe(_fn)

    assert events_module._subscribers.count(_fn) == 1
    events_module._subscribers.remove(_fn)
