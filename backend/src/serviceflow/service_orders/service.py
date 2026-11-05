"""Service order operations: numbering, transitions (docs/02 rules), BR-2 unlock,
warranty returns. Every change publishes a domain event → timeline (ADR-011)."""

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from business_os.identity import contracts as identity_contracts
from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.events import DomainEvent, publish
from business_os.shared_kernel.ids import new_id
from serviceflow.assets import service as assets_service
from serviceflow.customers import service as customers_service
from serviceflow.service_orders import lines as _lines
from serviceflow.service_orders import protocol, statuses
from serviceflow.service_orders.models import Diagnosis, DocumentSequence, ServiceOrder

UNLOCK_WINDOW = timedelta(hours=24)


class OrderError(Exception):
    def __init__(self, message_key: str, status: int = 409,
                params: dict[str, Any] | None = None) -> None:
        self.message_key = message_key
        self.status = status
        self.params = params or {}


def _now() -> datetime:
    return datetime.now(UTC)


# Invoice numbering must be continuous across calendar years — legally
# required, not a product choice (docs/ACCOUNTANT_REVIEW.md §1: ППЗДДС/ЗДДС
# "без пропуски и дублиране" — no gaps, no duplicates, ever, for the life of
# the company's registration; confirmed directly against NRA's own published
# guidance). `document_sequences.year` stays NOT NULL — no migration — but
# for kind="invoice" it is never a calendar year: it is reinterpreted as a
# *series/epoch* number. Epoch 0 is the company's one and only invoice
# series for as long as the product exists; Bulgarian practice only starts a
# new series after the entire 10-digit range is exhausted, and only after a
# written notice to NRA (docs/ACCOUNTANT_REVIEW.md §1) — a rare, deliberate,
# out-of-band event, never something calendar time triggers on its own. The
# only sanctioned way to allocate an invoice number is next_invoice_number()
# below — it is the sole place this constant is used, so the convention
# cannot be silently misused as a real year by another call site.
INVOICE_SEQUENCE_EPOCH = 0


def allocate_sequence(db: Session, ctx: TenantContext, *, kind: str, year: int) -> int:
    """Atomic per-(company, kind, year) counter (docs/08's frozen gaplessness
    point; hardened per ADR-BOS-005). A single INSERT ... ON CONFLICT DO
    UPDATE is atomic in Postgres: unlike a SELECT-then-INSERT pair, there is
    no window where two concurrent first-allocations for the same key can
    both observe "no row" and both attempt the insert. The loser blocks on
    the unique index (uq_document_sequences_key) until the winner's
    transaction resolves, then applies its own increment on top instead of
    raising IntegrityError — so no number is ever repeated, lost, or
    skipped, and already-existing rows keep the same until-commit row lock a
    SELECT ... FOR UPDATE would have held.

    Returns the raw allocated counter — no document-specific formatting.
    `kind` and `year` are both required (no defaults) so a caller can never
    accidentally fall back to an unintended sequence; see next_order_number
    and next_invoice_number for the two sanctioned call shapes."""
    stmt = (
        pg_insert(DocumentSequence)
        .values(id=new_id(), company_id=ctx.company_id, kind=kind, year=year, current=1)
        .on_conflict_do_update(
            index_elements=[
                DocumentSequence.company_id, DocumentSequence.kind, DocumentSequence.year,
            ],
            set_={"current": DocumentSequence.current + 1},
        )
        .returning(DocumentSequence.current)
    )
    return db.execute(stmt).scalar_one()


def next_order_number(db: Session, ctx: TenantContext) -> str:
    """Per-company yearly order sequence (docs/08), "{year}-{00001}" —
    resets every calendar year by design. Orders carry no numbering-
    continuity legal requirement (unlike invoices, see next_invoice_number),
    so the year-scoped key is correct and unchanged here."""
    year = _now().year
    current = allocate_sequence(db, ctx, kind="order", year=year)
    return f"{year}-{current:05d}"


def next_invoice_number(db: Session, ctx: TenantContext) -> str:
    """Per-company invoice sequence, continuous across calendar years
    (see INVOICE_SEQUENCE_EPOCH above — legally required, not a product
    choice). Ten Arabic digits, zero-padded, no year prefix and no dash —
    the ЗДДС чл. 113/114 / ППЗДДС чл. 78 format
    (docs/ACCOUNTANT_REVIEW.md §1)."""
    current = allocate_sequence(db, ctx, kind="invoice", year=INVOICE_SEQUENCE_EPOCH)
    return f"{current:010d}"


def _event(db: Session, ctx: TenantContext, order: ServiceOrder, type_: str,
           data: dict[str, Any] | None = None) -> None:
    publish(db, DomainEvent(
        type=type_, company_id=ctx.company_id, actor_user_id=ctx.user_id,
        subject_id=order.id, data=data or {},
    ))


def find_open_order_for_asset(db: Session, ctx: TenantContext,
                              asset_id: uuid.UUID) -> ServiceOrder | None:
    """Q6: an asset with any open order (every non-terminal status, incl.
    "ready" — `statuses.OPEN`) blocks a new one, for every asset type, not
    just vehicles. Newest first in the unlikely case more than one somehow
    exists already."""
    stmt = (
        scoped(select(ServiceOrder), ServiceOrder, ctx)
        .where(ServiceOrder.asset_id == asset_id, ServiceOrder.status_code.in_(statuses.OPEN))
        .order_by(ServiceOrder.created_at.desc())
    )
    return db.scalar(stmt)


def _max_mileage_for_asset(db: Session, ctx: TenantContext, asset_id: uuid.UUID) -> int | None:
    """Q9's floor a new order's mileage must be >= (unless Owner-bypassed,
    Q10): the true highest mileage **ever** recorded for this asset — not
    just its latest order's value, since a Q10 bypass can deliberately make
    a later order's own mileage lower than an earlier true maximum. Falls
    back to the legacy `Asset.field_values["mileage"]` only when no order
    has recorded one yet (same fallback `GET .../service-history` uses)."""
    highest = db.scalar(
        scoped(select(func.max(ServiceOrder.mileage)), ServiceOrder, ctx)
        .where(ServiceOrder.asset_id == asset_id)
    )
    if highest is not None:
        return highest
    asset = assets_service.get(db, ctx, asset_id)
    legacy = asset.field_values.get("mileage") if asset else None
    return int(legacy) if isinstance(legacy, int | float) else None


def create(db: Session, ctx: TenantContext, *, customer_id: uuid.UUID,
           asset_id: uuid.UUID, complaint: str, priority: str = "normal",
           promised_on: Any = None, technician_id: uuid.UUID | None = None,
           origin_order_id: uuid.UUID | None = None,
           mileage: int | None = None, mileage_confirmed_lower: bool = False,
           mileage_override_comment: str | None = None,
           delivery_method: str | None = None,
           delivery_address: dict[str, Any] | None = None) -> ServiceOrder:
    # Q6: checked before number allocation, same discipline commercial.
    # service.issue() uses for its own pre-allocation validation, so a
    # rejected request never consumes an order number.
    existing_open = find_open_order_for_asset(db, ctx, asset_id)
    if existing_open is not None:
        raise OrderError("errors.orders.open_order_exists", status=409,
                         params={"number": existing_open.number})

    # Q9/Q10 (order-workflow-revamp WP-D): mileage is optional for every
    # profile now (reverses Cleanup batch Issue 26's automotive-required
    # rule) — but when given, it must not go backwards unless the Owner
    # explicitly confirms a lower reading with a mandatory comment. Each
    # distinct failure gets its own message key, same layered-checks style
    # `unlock()` above already uses (owner_required is a flat 403 — a
    # non-Owner has no bypass at all, full stop).
    is_lower_confirmed = False
    previous_max = _max_mileage_for_asset(db, ctx, asset_id) if mileage is not None else None
    if previous_max is not None and mileage is not None and mileage < previous_max:
        if not ctx.is_owner:
            raise OrderError("errors.auth.owner_required", status=403)
        if not mileage_confirmed_lower:
            raise OrderError("errors.orders.mileage_lower_than_previous", status=409,
                             params={"previous": previous_max})
        if not (mileage_override_comment or "").strip():
            raise OrderError("errors.orders.mileage_override_comment_required", status=400)
        is_lower_confirmed = True

    order = ServiceOrder(
        company_id=ctx.company_id, number=next_order_number(db, ctx),
        customer_id=customer_id, asset_id=asset_id, complaint=complaint,
        status_code="received", priority=priority, promised_on=promised_on,
        technician_id=technician_id, origin_order_id=origin_order_id,
        status_changed_at=_now(), created_by=ctx.user_id, mileage=mileage,
        mileage_confirmed_lower=is_lower_confirmed,
        delivery_method=delivery_method, delivery_address=delivery_address,
    )
    db.add(order)
    db.flush()
    _event(db, ctx, order, "order_created", {
        "number": order.number,
        **({"origin_order_id": str(origin_order_id)} if origin_order_id else {}),
    })
    if technician_id is not None:
        _event(db, ctx, order, "technician_assigned", {"technician_id": str(technician_id)})
    if is_lower_confirmed:
        _event(db, ctx, order, "mileage_override_confirmed", {
            "reading": mileage, "previous_max": previous_max,
            "comment": (mileage_override_comment or "").strip(),
        })
    db.commit()
    return order


def get(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> ServiceOrder | None:
    return db.scalar(
        scoped(select(ServiceOrder), ServiceOrder, ctx).where(ServiceOrder.id == order_id)
    )


def get_many(db: Session, ctx: TenantContext,
            order_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, ServiceOrder]:
    """Batch counterpart to get() — one query, not N (same idiom as
    customers.service.get_many/assets.service.get_many)."""
    ids = set(order_ids)
    if not ids:
        return {}
    rows = db.scalars(
        scoped(select(ServiceOrder), ServiceOrder, ctx).where(ServiceOrder.id.in_(ids))
    )
    return {o.id: o for o in rows}


def list_orders_for_asset(db: Session, ctx: TenantContext, asset_id: uuid.UUID,
                          limit: int = 200) -> list[ServiceOrder]:
    """Every order against this asset, newest first — archived included and
    NOT filtered by customer_id (Wave 3 Issues 21/26/27: a vehicle's service
    history must survive an ownership change, so it is keyed on asset_id
    alone, exactly like `ServiceOrder.asset_id` already is). The tenant scope
    from `scoped()` is the only filter — this is deliberately company-wide,
    not customer-scoped."""
    stmt = scoped(select(ServiceOrder), ServiceOrder, ctx).where(
        ServiceOrder.asset_id == asset_id
    )
    return list(db.scalars(stmt.order_by(ServiceOrder.created_at.desc()).limit(limit)))


def list_order_ids_for_customer(db: Session, ctx: TenantContext,
                                customer_id: uuid.UUID) -> list[uuid.UUID]:
    """Every order id belonging to this customer, archived or not — an
    invoice filter (Issue 39) must never hide a customer's historical
    invoices just because their order was later archived. ID-only and
    unpaginated: one shop's one customer's order count is naturally small,
    and this exists purely as an IN-list source for another module's own
    paginated query (commercial.service.list_invoices), never rendered
    itself."""
    return list(db.scalars(
        scoped(select(ServiceOrder.id), ServiceOrder, ctx)
        .where(ServiceOrder.customer_id == customer_id)
    ))


def technician_load(db: Session, ctx: TenantContext) -> dict[uuid.UUID, int]:
    """Orders per technician in `statuses.TECHNICIAN_LOAD` (WP-F/Q22). Only
    technicians with at least one such order appear; the picker treats a
    missing one as free. Archived orders are terminal by rule (`archive`), so
    they never match these statuses and need no extra filter."""
    stmt = (
        scoped(select(ServiceOrder.technician_id, func.count()), ServiceOrder, ctx)
        .where(ServiceOrder.technician_id.is_not(None),
               ServiceOrder.status_code.in_(statuses.TECHNICIAN_LOAD))
        .group_by(ServiceOrder.technician_id)
    )
    return {tid: n for tid, n in db.execute(stmt).tuples() if tid is not None}


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


def _build_completion_snapshot(db: Session, ctx: TenantContext,
                               order: ServiceOrder) -> dict[str, Any]:
    """Wave 4 Issue 7: independent JSON, frozen at delivery time — same
    discipline `commercial.service.issue()` uses for `Invoice.seller`/
    `.buyer` (never a reference into live Customer/Company/Asset/line rows,
    so a later edit to any of them can never retroactively change what a
    reprinted delivery protocol shows). Reads `serviceflow.customers`/
    `serviceflow.assets` directly (the same vertical as service_orders,
    per docs/business-os/04 rule R6 — service_orders.contracts' own
    docstring already documents this as sanctioned) and
    `business_os.identity.contracts` (identity's public surface) — never
    `serviceflow.commercial`, which stays untouched by this feature."""
    customer = customers_service.get(db, ctx, order.customer_id)
    asset = assets_service.get(db, ctx, order.asset_id)
    asset_type = (assets_service.get_type_by_id(db, ctx, asset.asset_type_id)
                 if asset is not None else None)
    company = identity_contracts.get_company_profile(db, ctx.company_id)
    warranty_defaults = identity_contracts.get_warranty_defaults(db, ctx.company_id)
    diagnosis = get_diagnosis(db, ctx, order.id)
    technician_name = (
        identity_contracts.get_user_name(db, ctx.company_id, order.technician_id)
        if order.technician_id is not None else None
    )

    identifiers: list[list[str]] = []
    if asset is not None and asset_type is not None:
        identifiers = [
            [fd["label_bg"], str(asset.field_values[fd["key"]])]
            for fd in asset_type.field_defs
            if fd.get("identifier_kind") and asset.field_values.get(fd["key"])
        ]

    return {
        "order": {
            "number": order.number,
            "completed_at": _now().isoformat(),
            "complaint": order.complaint,
            "mileage": order.mileage,
            "warranty_days": order.warranty_days,
        },
        "customer": {
            "name": customer.name if customer is not None else "",
            "phone": customer.phone if customer is not None else "",
        },
        "company": {
            "name": company.name,
            "address": str(company.requisites.get("address", "")),
            "phone": str(company.requisites.get("phone", "")),
            # Issue 04: frozen at completion time, same reasoning as every
            # other field here — a later edit to the company's warranty
            # terms must never retroactively change what a reprinted
            # protocol shows.
            "warranty_standard_term": warranty_defaults.get("standard_term"),
            "warranty_conditions": warranty_defaults.get("conditions"),
            "warranty_text": warranty_defaults.get("text"),
            "warranty_additional_conditions": warranty_defaults.get("additional_conditions"),
        },
        "asset": {
            "type_name": asset_type.name_bg if asset_type is not None else "",
            "label": asset.label if asset is not None else "",
            "identifiers": identifiers,
        },
        "diagnosis": {
            "observed": diagnosis.observed, "cause": diagnosis.cause,
            "recommendation": diagnosis.recommendation,
        } if diagnosis is not None else None,
        "labor_lines": [
            # qty is Decimal (order-workflow-revamp WP-I) — not JSON-
            # serializable directly, same reason unit_price is already str().
            {"description": line.description, "qty": str(line.qty),
             "unit_price": str(line.unit_price)}
            for line in _lines.list_labor_lines(db, ctx, order.id)
        ],
        "part_lines": [
            # order-workflow-revamp WP-J: `has_warranty` (boolean), not the
            # retired `warranty_days` — a snapshot frozen before this change
            # still has the old key and keeps printing its months forever
            # (Q14c); protocol.py's build_delivery_protocol_data() is what
            # reads both shapes.
            {"name": p.name, "qty": p.qty, "unit_price": str(p.unit_price),
             "has_warranty": p.has_warranty}
            for p in _lines.list_part_lines(db, ctx, order.id)
        ],
        "accessories": [
            {"name": a.name, "qty": a.qty, "returned": a.returned}
            for a in _lines.list_accessories(db, ctx, order.id)
        ],
        "total": str(_lines.order_totals(db, ctx, order.id)),
        "technician_name": technician_name,
    }


def change_status(db: Session, ctx: TenantContext, order: ServiceOrder, *, to: str,
                  reason: str | None = None, approval: dict[str, Any] | None = None,
                  warranty_days: int | None = None,
                  technician_id: uuid.UUID | None = None) -> tuple[ServiceOrder, str | None]:
    """The single entry point for status changes (docs/09: Kanban is just a client).

    Returns (order, warning) where warning is "skip" for WARN transitions.

    order-workflow-revamp WP-G (Q2b): `technician_id`, when given, is applied
    *before* the technician-required precondition below is checked — this is
    how ПРИЕМИ (received -> diagnostics) lets a caller pick a technician and
    accept in one request when intake didn't already set one. Not routed
    through `assign_technician()` (that function is reserved for the
    standalone PATCH /orders/{id} path, which also emits its own
    `technician_assigned` event) — applying it here inline avoids a second,
    redundant event for what is really one user action.
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
    # order-workflow-revamp WP-G (Q3/Q3b): a backward move (Чака клиент/Чака
    # части/Ремонт -> Диагностика, Готова -> Ремонт) always needs its own
    # mandatory reason, regardless of the "cancelled"/"declined" rule above
    # (which is cell-specific, not direction-specific).
    if verdict == statuses.BACK and not (reason and reason.strip()):
        raise OrderError("errors.orders.reason_required", status=400)
    if technician_id is not None:
        order.technician_id = technician_id
    # order-workflow-revamp WP-G (Q2a): a technician must already be
    # assigned to enter Диагностика or any later WORKING status — checked
    # generically on the *target* status's kind, not hardcoded to
    # "diagnostics" alone, so it also catches a legacy order (no technician
    # on file, predating this rule) attempting its next transition into
    # Ремонт from a waiting status, per Q2a's "every later working status."
    # Every WORKING status past "received" is only reachable by first
    # passing through "diagnostics" (see `_FORWARD`/`_BACKWARD` in
    # statuses.py), so this one generic check is sufficient — no separate
    # check is needed per working status.
    if statuses.kind_of(to) == statuses.Kind.WORKING and order.technician_id is None:
        raise OrderError("errors.orders.technician_required", status=400)
    # order-workflow-revamp WP-G: BR-7's approval gate is specific to
    # *forward* exits from Чака клиент (the customer's decision on the
    # estimate) — the backward move back to Диагностика already carries its
    # own mandatory reason above and isn't "the customer decided," so it's
    # deliberately excluded here (verdict == BACK skips this block
    # entirely). Not an explicit PO decision — the audit didn't address the
    # interaction between Q3b's reason and BR-7's approval, so this is this
    # session's own scope call; see AUDIT.md's WP-G completion entry.
    if order.status_code == "waiting_customer" and verdict != statuses.BACK:
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
        if to == "completed":
            order.completed_at = _now()
            if warranty_days is not None:
                # Explicit — including 0 ("Без гаранция") — always wins,
                # even on a later redeliver after unlock.
                order.warranty_days = warranty_days
            elif order.warranty_days is None:
                # Cleanup batch Issue 7: omitted/unspecified and nothing
                # already stored — the server, not just the frontend
                # prefill, applies the company's configured labor/work
                # default when one exists. Gated on "nothing already
                # stored" so a later change to the company default can
                # never retroactively mutate a value this order already
                # received at an earlier delivery.
                default = identity_contracts.get_warranty_defaults(
                    db, ctx.company_id,
                )["labor_days"]
                if default is not None:
                    order.warranty_days = default
            # Wave 4 Issue 7: built once, at the moment of delivery, from
            # whatever is true right now — never rebuilt afterward (an
            # unlock+redeliver on the same order would otherwise silently
            # overwrite the original delivery's record, which is exactly
            # what "reproducible regardless of later changes" rules out).
            if order.completion_snapshot is None:
                order.completion_snapshot = _build_completion_snapshot(db, ctx, order)
            _event(db, ctx, order, "order_completed",
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
    order.completed_at = None
    order.row_version += 1
    _event(db, ctx, order, "order_unlocked", {"from": frm, "to": back_to, "reason": reason})
    db.commit()
    return order


def warranty_return(db: Session, ctx: TenantContext, original: ServiceOrder,
                    complaint: str) -> ServiceOrder:
    if statuses.kind_of(original.status_code) != statuses.Kind.TERMINAL_SUCCESS:
        raise OrderError("errors.orders.warranty_needs_completed")
    new_order = create(
        db, ctx, customer_id=original.customer_id, asset_id=original.asset_id,
        complaint=complaint, priority="high", origin_order_id=original.id,
    )
    _event(db, ctx, original, "warranty_return_opened",
           {"new_order_id": str(new_order.id), "new_number": new_order.number})
    db.commit()
    return new_order


def send_completion_protocol_email(db: Session, ctx: TenantContext, order: ServiceOrder,
                                   *, include_warranty: bool) -> None:
    """Issue 03 (audit correction): emails the completion protocol PDF —
    reads the exact same frozen `completion_snapshot` the print action
    reads, never live data (same discipline as `GET .../protocol.pdf?
    type=delivery`). Raises `OrderError` for every failure mode; never
    silently no-ops. This differs on purpose from `identity.mail`'s
    password-reset posture, which deliberately hides send failure from the
    caller for account-enumeration reasons — there's no equivalent concern
    here: an authenticated shop employee explicitly asked to send this and
    needs to know if it didn't go out."""
    if order.completion_snapshot is None:
        raise OrderError("errors.protocol.delivery_unavailable", status=404)

    customer = customers_service.get(db, ctx, order.customer_id)
    if customer is None or not customer.email:
        raise OrderError("errors.protocol.email_missing_customer_email", status=400)

    pdf_bytes = protocol.generate_delivery_protocol(
        protocol.build_delivery_protocol_data(order.completion_snapshot),
        include_warranty=include_warranty,
    )
    company = identity_contracts.get_company_profile(db, ctx.company_id)
    subject = f"Протокол за поръчка № {order.number} — {company.name}"
    body = f"Прилагаме протокола за Вашата поръчка № {order.number}.\n\n{company.name}"
    sent = identity_contracts.send_email_with_attachment(
        customer.email, subject, body, f"protokol-{order.number}.pdf", pdf_bytes,
    )
    if not sent:
        raise OrderError("errors.protocol.email_send_failed", status=502)


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
