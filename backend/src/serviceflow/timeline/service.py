"""Timeline: subscribes to domain events, offers tenant-scoped reads. Never edits."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.events import DomainEvent, subscribe
from serviceflow.timeline.models import TimelineEvent


@subscribe
def _record(db: Session, event: DomainEvent) -> None:
    if event.order_id is None:
        return
    db.add(TimelineEvent(
        company_id=event.company_id, order_id=event.order_id,
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
