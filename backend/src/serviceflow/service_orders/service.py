"""Service order operations: numbering, transitions (docs/02 rules), BR-2 unlock,
warranty returns. Every change publishes a domain event → timeline (ADR-011)."""

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.events import DomainEvent, publish
from serviceflow.service_orders import statuses
from serviceflow.service_orders.models import Diagnosis, DocumentSequence, ServiceOrder

UNLOCK_WINDOW = timedelta(hours=24)


class OrderError(Exception):
    def __init__(self, message_key: str, status: int = 409) -> None:
        self.message_key = message_key
        self.status = status


def _now() -> datetime:
    return datetime.now(UTC)


def next_number(db: Session, ctx: TenantContext, kind: str = "order") -> str:
    """Per-company yearly sequence. Row lock serializes concurrent intakes."""
    year = _now().year
    seq = db.scalar(
        select(DocumentSequence)
        .where(DocumentSequence.company_id == ctx.company_id,
               DocumentSequence.kind == kind, DocumentSequence.year == year)
        .with_for_update()
    )
    if seq is None:
        seq = DocumentSequence(company_id=ctx.company_id, kind=kind, year=year, current=0)
        db.add(seq)
        db.flush()
        seq = db.scalar(
            select(DocumentSequence)
            .where(DocumentSequence.id == seq.id)
            .with_for_update()
        )
        assert seq is not None
    seq.current += 1
    return f"{year}-{seq.current:05d}"


def _event(db: Session, ctx: TenantContext, order: ServiceOrder, type_: str,
           data: dict[str, Any] | None = None) -> None:
    publish(db, DomainEvent(
        type=type_, company_id=ctx.company_id, actor_user_id=ctx.user_id,
        subject_id=order.id, data=data or {},
    ))


def create(db: Session, ctx: TenantContext, *, customer_id: uuid.UUID,
           asset_id: uuid.UUID, complaint: str, priority: str = "normal",
           promised_on: Any = None, technician_id: uuid.UUID | None = None,
           origin_order_id: uuid.UUID | None = None) -> ServiceOrder:
    order = ServiceOrder(
        company_id=ctx.company_id, number=next_number(db, ctx),
        customer_id=customer_id, asset_id=asset_id, complaint=complaint,
        status_code="received", priority=priority, promised_on=promised_on,
        technician_id=technician_id, origin_order_id=origin_order_id,
        status_changed_at=_now(), created_by=ctx.user_id,
    )
    db.add(order)
    db.flush()
    _event(db, ctx, order, "order_created", {
        "number": order.number,
        **({"origin_order_id": str(origin_order_id)} if origin_order_id else {}),
    })
    if technician_id is not None:
        _event(db, ctx, order, "technician_assigned", {"technician_id": str(technician_id)})
    db.commit()
    return order


def get(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> ServiceOrder | None:
    return db.scalar(
        scoped(select(ServiceOrder), ServiceOrder, ctx).where(ServiceOrder.id == order_id)
    )


def list_orders(db: Session, ctx: TenantContext, *, state: str = "open",
                status_code: str | None = None, technician_id: uuid.UUID | None = None,
                customer_id: uuid.UUID | None = None,
                priority: str | None = None, overdue: bool = False,
                include_archived: bool = False, limit: int = 200) -> list[ServiceOrder]:
    stmt = scoped(select(ServiceOrder), ServiceOrder, ctx)
    if not include_archived:
        stmt = stmt.where(ServiceOrder.archived_at.is_(None))
    if state == "open":
        stmt = stmt.where(ServiceOrder.status_code.in_(statuses.OPEN))
    elif state == "terminal":
        stmt = stmt.where(ServiceOrder.status_code.in_(statuses.TERMINAL))
    if status_code:
        stmt = stmt.where(ServiceOrder.status_code == status_code)
    if technician_id:
        stmt = stmt.where(ServiceOrder.technician_id == technician_id)
    if customer_id:
        stmt = stmt.where(ServiceOrder.customer_id == customer_id)
    if priority:
        stmt = stmt.where(ServiceOrder.priority == priority)
    if overdue:
        active = {c for c in statuses.OPEN if statuses.kind_of(c) != statuses.Kind.READY}
        stmt = stmt.where(
            ServiceOrder.promised_on.is_not(None),
            ServiceOrder.promised_on < _now().date(),
            ServiceOrder.status_code.in_(active),
        )
    return list(db.scalars(stmt.order_by(ServiceOrder.created_at.desc()).limit(limit)))


def count_active_by_customer(db: Session, ctx: TenantContext,
                             customer_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Batch count for the customers list row (docs/15 §6.7) — one query, not N."""
    ids = set(customer_ids)
    if not ids:
        return {}
    rows = db.execute(
        scoped(select(ServiceOrder.customer_id, func.count()), ServiceOrder, ctx)
        .where(
            ServiceOrder.customer_id.in_(ids),
            ServiceOrder.status_code.in_(statuses.OPEN),
            ServiceOrder.archived_at.is_(None),
        )
        .group_by(ServiceOrder.customer_id)
    )
    return {row[0]: row[1] for row in rows}


def get_diagnosis(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> Diagnosis | None:
    return db.scalar(
        scoped(select(Diagnosis), Diagnosis, ctx).where(Diagnosis.order_id == order_id)
    )


def put_diagnosis(db: Session, ctx: TenantContext, order: ServiceOrder,
                  fields: dict[str, Any]) -> Diagnosis:
    """Create-or-replace in place (docs/01: no versioning, timeline carries history)."""
    diagnosis = get_diagnosis(db, ctx, order.id)
    is_new = diagnosis is None
    if diagnosis is None:
        diagnosis = Diagnosis(company_id=ctx.company_id, order_id=order.id)
        db.add(diagnosis)
    for key, value in fields.items():
        setattr(diagnosis, key, value)
    cost = float(diagnosis.estimated_cost) if diagnosis.estimated_cost is not None else None
    _event(db, ctx, order, "diagnosis_recorded" if is_new else "diagnosis_updated", {
        "recommendation": diagnosis.recommendation, "estimated_cost": cost,
    })
    db.commit()
    return diagnosis


def _persist_diagnosis_approval(db: Session, ctx: TenantContext, order: ServiceOrder,
                                approval: dict[str, Any]) -> None:
    diagnosis = get_diagnosis(db, ctx, order.id)
    if diagnosis is None:
        return  # approval recorded on the order event even if no diagnosis exists yet
    diagnosis.approval = {
        **approval, "by_user": str(ctx.user_id), "at": _now().isoformat(),
    }


def change_status(db: Session, ctx: TenantContext, order: ServiceOrder, *, to: str,
                  reason: str | None = None, approval: dict[str, Any] | None = None,
                  warranty_days: int | None = None) -> tuple[ServiceOrder, str | None]:
    """The single entry point for status changes (docs/09: Kanban is just a client).

    Returns (order, warning) where warning is "skip" for WARN transitions.
    """
    if order.archived_at is not None:
        raise OrderError("errors.orders.archived")
    verdict = statuses.check_transition(order.status_code, to)
    if verdict == statuses.NO:
        raise OrderError("errors.orders.invalid_transition")

    # Business rules riding on transitions (docs/02 §2):
    if to == "cancelled" and not ctx.is_owner:
        raise OrderError("errors.auth.owner_required", status=403)
    if to in ("cancelled", "declined") and not (reason and reason.strip()):
        raise OrderError("errors.orders.reason_required", status=400)
    if order.status_code == "waiting_customer":
        if to == "declined":
            _event(db, ctx, order, "estimate_rejected", {"reason": reason})
            _persist_diagnosis_approval(db, ctx, order, {
                "approved": False, "reason": reason, "channel": None, "amount": None,
            })
        elif to not in statuses.TERMINAL:
            if not approval or approval.get("approved") is not True:
                raise OrderError("errors.orders.approval_required", status=400)
            _event(db, ctx, order, "estimate_approved", {
                "channel": str(approval.get("channel", "")),
                "amount": approval.get("amount"),
            })
            _persist_diagnosis_approval(db, ctx, order, {
                "approved": True, "channel": approval.get("channel"),
                "amount": approval.get("amount"),
            })

    prev = order.status_code
    order.status_code = to
    order.status_changed_at = _now()
    order.row_version += 1
    if to in statuses.TERMINAL:
        order.prev_status_code = prev
        order.terminal_at = _now()
        order.terminal_reason = reason
        if to == "delivered":
            order.delivered_at = _now()
            if warranty_days is not None:
                order.warranty_days = warranty_days
            _event(db, ctx, order, "order_delivered",
                   {"warranty_days": order.warranty_days})

    warning = "skip" if verdict == statuses.WARN else None
    _event(db, ctx, order, "status_changed",
           {"from": prev, "to": to, **({"warning": warning} if warning else {}),
            **({"reason": reason} if reason else {})})
    db.commit()
    return order, warning


def unlock(db: Session, ctx: TenantContext, order: ServiceOrder,
           reason: str) -> ServiceOrder:
    """BR-2 amendment: Owner-only, ≤24h, back to the pre-terminal status."""
    if not ctx.is_owner:
        raise OrderError("errors.auth.owner_required", status=403)
    if order.status_code not in statuses.TERMINAL or order.terminal_at is None:
        raise OrderError("errors.orders.not_terminal")
    if order.archived_at is not None:
        raise OrderError("errors.orders.archived")
    terminal_at = order.terminal_at
    if terminal_at.tzinfo is None:
        terminal_at = terminal_at.replace(tzinfo=UTC)
    if _now() - terminal_at > UNLOCK_WINDOW:
        raise OrderError("errors.orders.unlock_window_expired")
    if not reason.strip():
        raise OrderError("errors.orders.reason_required", status=400)

    back_to = order.prev_status_code or "received"
    frm = order.status_code
    order.status_code = back_to
    order.status_changed_at = _now()
    order.terminal_at = None
    order.terminal_reason = None
    order.prev_status_code = None
    order.delivered_at = None
    order.row_version += 1
    _event(db, ctx, order, "order_unlocked", {"from": frm, "to": back_to, "reason": reason})
    db.commit()
    return order


def warranty_return(db: Session, ctx: TenantContext, original: ServiceOrder,
                    complaint: str) -> ServiceOrder:
    if statuses.kind_of(original.status_code) != statuses.Kind.TERMINAL_SUCCESS:
        raise OrderError("errors.orders.warranty_needs_delivered")
    new_order = create(
        db, ctx, customer_id=original.customer_id, asset_id=original.asset_id,
        complaint=complaint, priority="high", origin_order_id=original.id,
    )
    _event(db, ctx, original, "warranty_return_opened",
           {"new_order_id": str(new_order.id), "new_number": new_order.number})
    db.commit()
    return new_order


def archive(db: Session, ctx: TenantContext, order: ServiceOrder) -> None:
    if order.status_code not in statuses.TERMINAL:
        raise OrderError("errors.orders.not_terminal")
    order.archived_at = _now()
    _event(db, ctx, order, "order_archived", {})
    db.commit()


def assign_technician(db: Session, ctx: TenantContext, order: ServiceOrder,
                      technician_id: uuid.UUID | None) -> None:
    order.technician_id = technician_id
    order.row_version += 1
    _event(db, ctx, order, "technician_assigned",
           {"technician_id": str(technician_id) if technician_id else None})
