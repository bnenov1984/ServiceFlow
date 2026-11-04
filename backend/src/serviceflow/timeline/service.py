"""Timeline: subscribes to domain events, offers tenant-scoped reads. Never edits."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.events import DomainEvent, subscribe
from serviceflow.timeline.models import TimelineEvent

# The exhaustive, hand-maintained set of event `type` strings this ServiceFlow
# subscriber understands (docs/01 §5's conceptual catalog, real snake_case
# names per BOS-11 F2). The shared bus (business_os.shared_kernel.events)
# dispatches every published event to every subscriber regardless of
# publisher (BOS-06: "subscribes: [all]") — after ADR-BOS-007 made
# DomainEvent.subject_id a neutral reference usable by any module, a
# subscriber that reacted to "any event with a subject_id" would try to
# interpret a non-ServiceFlow id (e.g. a future professional_services
# assignment id) as an order id and violate TimelineEvent.order_id's FK to
# service_orders. Gate on the type allowlist first: an unrecognised type is
# ignored outright, never reaching the TimelineEvent construction below.
# Adding a new ServiceFlow event type means adding its string here too.
KNOWN_EVENT_TYPES = frozenset({
    "order_created", "technician_assigned", "diagnosis_recorded", "diagnosis_updated",
    "estimate_rejected", "estimate_approved", "order_delivered", "order_completed",
    "status_changed",
    "order_unlocked", "warranty_return_opened", "order_archived",
    "mileage_override_confirmed",
    "part_added", "part_ordered", "part_received", "part_state_changed", "labor_added",
    "task_created", "task_completed", "task_reopened",
    "attachment_added", "attachment_deleted",
    "note_or_contact_recorded",
    "payment_recorded", "payment_refunded",
    "invoice_issued", "invoice_annulled", "invoice_linked",
})


@subscribe
def _record(db: Session, event: DomainEvent) -> None:
    if event.type not in KNOWN_EVENT_TYPES or event.subject_id is None:
        return
    db.add(TimelineEvent(
        company_id=event.company_id, order_id=event.subject_id,
        event_type=event.type, actor_user_id=event.actor_user_id, data=event.data,
    ))


def for_order(db: Session, ctx: TenantContext, order_id: uuid.UUID,
              limit: int = 200) -> list[TimelineEvent]:
    stmt = (
        scoped(select(TimelineEvent), TimelineEvent, ctx)
        .where(TimelineEvent.order_id == order_id)
        .order_by(TimelineEvent.created_at.desc(), TimelineEvent.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
