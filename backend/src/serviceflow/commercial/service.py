"""Payment recording (docs/01 §Payment) and Invoice drafts + Issue
(docs/01 §Invoice).

Money totals stay derived, never stored (BR-3): paid_amount and balance are
computed here, not persisted. Invoice draft creation/editing is this file's
second part; `issue()` is the third; `get_issued()` (the PDF endpoint's
fetch-and-status-check, commercial/pdf.py does the actual rendering) is the
fourth; `list_invoices()`'s pagination + `draft_totals()` (batch, one query
per page regardless of row count) back the central invoice list
(commercial/router.py's `list_invoices` endpoint) as the fifth. Buyer support
covers individuals and domestic company buyers (VAT-registered or not,
docs/ACCOUNTANT_REVIEW.md §4 B1) — see `_buyer_snapshot()`. Seller support
covers non-VAT-registered companies (`vat_mode="not_registered"`, `vat=0`)
and VAT-registered companies at the single standard rate (`vat_mode=
"registered"`, `STANDARD_VAT_RATE` — docs/ACCOUNTANT_REVIEW.md §6, VAT
rounding recorded there as an implemented product decision pending
professional confirmation). `annul()` (Wave 6 Issue 30, case-A
documentation-error correction only, ЗДДС чл. 116) is the sixth — a pure
status+metadata transition on an already-issued invoice, never touching its
frozen content or number. `create_manual_draft()` (Wave 6 Issue 30, second
half) is the seventh — an order-less draft whose buyer identity is a direct
`customer_id` instead of an order's; `issue()` forks its buyer resolution
on which one a given row carries, but is otherwise the exact same one
engine for both. Reissue-linkage, cross-border B2B, mixed VAT rates,
reverse charge, 0%-rated supplies, and credit/debit notes are still later
slices (see commercial/models.py docstring and docs/ACCOUNTANT_REVIEW.md's
'RepairFlow Invoice V1 Freeze' §5, Phase-A scope)."""

import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from business_os.identity import contracts as identity_contracts
from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.events import DomainEvent, publish
from business_os.shared_kernel.normalize import (
    derive_seller_vat_number,
    is_valid_eik,
    is_valid_vat_number,
    normalize_eik,
    normalize_vat_number,
)
from serviceflow.commercial.models import Invoice, InvoiceLine, Payment
from serviceflow.customers import contracts as customers_contracts
from serviceflow.service_orders import contracts as orders_contracts

# Bulgaria's standard VAT rate (ЗДДС чл. 66) — the only rate V1 supports;
# no reduced rate/mixed rates/0%-rated supplies (docs/ACCOUNTANT_REVIEW.md
# §6). Numeric(5,2)-shaped to match InvoiceLine.vat_rate's column precision.
STANDARD_VAT_RATE = Decimal("20.00")
_CENT = Decimal("0.01")


class InvoiceError(Exception):
    def __init__(self, message_key: str, status: int = 409) -> None:
        self.message_key = message_key
        self.status = status


def _now() -> datetime:
    return datetime.now(UTC)


def add_payment(db: Session, ctx: TenantContext, order_id: uuid.UUID, *, amount: Decimal,
                method: str, is_refund: bool = False, note: str = "") -> Payment:
    payment = Payment(
        company_id=ctx.company_id, order_id=order_id, amount=amount, method=method,
        is_refund=is_refund, note=note, received_by=ctx.user_id, received_at=_now(),
    )
    db.add(payment)
    db.flush()
    publish(db, DomainEvent(
        type="payment_refunded" if is_refund else "payment_recorded",
        company_id=ctx.company_id, actor_user_id=ctx.user_id, subject_id=order_id,
        data={"amount": str(amount), "method": method},
    ))
    db.commit()
    return payment


def list_for_order(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> list[Payment]:
    return list(db.scalars(
        scoped(select(Payment), Payment, ctx)
        .where(Payment.order_id == order_id)
        .order_by(Payment.received_at)
    ))


def paid_amount(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> Decimal:
    """Net amount paid: recorded payments minus refunds (BR-3, docs/01 §Payment).
    Never stored — always derived from the payment records."""
    total = Decimal("0")
    for p in list_for_order(db, ctx, order_id):
        total += -p.amount if p.is_refund else p.amount
    return total


def balance(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> Decimal:
    """Outstanding balance: canonical order total (via service_orders'
    public contract — the single BR-3 total formula, never reimplemented
    here) minus net paid. May go negative (overpayment/credit) — docs/01
    does not prohibit it, so it is not rejected here."""
    return orders_contracts.get_order_total(db, ctx, order_id) - paid_amount(db, ctx, order_id)


# --- Invoice drafts (docs/01 §Invoice) --------------------------------------
# Draft only: create, list, read, replace lines. No issue/annul/reissue/PDF/
# VAT computation — see commercial/models.py's module docstring for why.

def create_draft(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> Invoice:
    """Prefilled from the order's part + labor lines via service_orders'
    public contract (docs/09: "draft prefilled from lines") — never
    service_orders.models/.lines directly. A one-time copy: later edits to
    the order's own lines do not retroactively change this draft, matching
    how the draft becomes an independently-editable document once created."""
    invoice = Invoice(company_id=ctx.company_id, order_id=order_id, status="draft")
    db.add(invoice)
    db.flush()
    for sort, line in enumerate(orders_contracts.get_order_lines(db, ctx, order_id)):
        db.add(InvoiceLine(
            company_id=ctx.company_id, invoice_id=invoice.id, description=line.description,
            qty=line.qty, unit_price=line.unit_price, source=line.source, sort=sort,
        ))
    db.commit()
    return invoice


def create_manual_draft(db: Session, ctx: TenantContext, customer_id: uuid.UUID) -> Invoice:
    """Wave 6 Issue 30 — the manual counterpart to `create_draft()`: no
    ServiceOrder involved at all, so nothing to prefill from (an empty
    draft; lines are added afterward through the exact same
    `replace_lines()` every order-generated draft already uses — no second
    editor, no second engine). `customer_id` becomes this row's buyer-
    identity source (see the Invoice model's XOR invariant); `issue()`
    resolves the buyer through it instead of through an order. The customer
    must exist in this tenant — same tenant-scoped existence check
    `create_invoice_draft`'s order lookup already gets for `order_id`."""
    if customers_contracts.get_customer_summary(db, ctx, customer_id) is None:
        raise InvoiceError("errors.invoices.customer_not_found", status=404)
    invoice = Invoice(
        company_id=ctx.company_id, order_id=None, customer_id=customer_id, status="draft",
    )
    db.add(invoice)
    db.commit()
    return invoice


def link_to_order(db: Session, ctx: TenantContext, invoice_id: uuid.UUID,
                  order_id: uuid.UUID) -> Invoice:
    """invoice-order-linking checkpoint 1 — attaches an existing manual
    invoice (`order_id IS NULL`, created via `create_manual_draft()`, draft
    or already issued) to a `ServiceOrder` after the fact. Deliberately not
    the same relationship as `annuls_invoice_id` (reissue linkage, unused in
    V1) — this is the first time a manual invoice gets an order at all.

    `customer_id` is intentionally left set afterward, not cleared — the
    Invoice model's "exactly one of order_id/customer_id" XOR docstring
    describes row *construction*, not an invariant this function needs to
    re-establish. Every downstream reader that forks on `order_id`
    (`issue()`'s buyer resolution, `_customer_name_for()`) checks the frozen
    `buyer` snapshot first once issued, so a post-issue link never changes
    which buyer was actually billed; the customer-match check below closes
    the same gap for a still-draft invoice.

    Sets a reference only, never touches lines/totals/status — issued
    invoices stay immutable in financial content (root CLAUDE.md rule 6)."""
    invoice = db.scalar(scoped(select(Invoice), Invoice, ctx).where(Invoice.id == invoice_id))
    if invoice is None:
        raise InvoiceError("errors.invoices.not_found", status=404)
    if invoice.order_id is not None:
        raise InvoiceError("errors.invoices.already_linked")

    order = orders_contracts.get_order_summary(db, ctx, order_id)
    if order is None:
        raise InvoiceError("errors.orders.not_found", status=404)
    if order.archived:
        raise InvoiceError("errors.orders.archived")
    if order.customer_id != invoice.customer_id:
        raise InvoiceError("errors.invoices.customer_mismatch")

    invoice.order_id = order_id
    invoice.row_version += 1
    publish(db, DomainEvent(
        type="invoice_linked", company_id=ctx.company_id, actor_user_id=ctx.user_id,
        subject_id=order_id, data={"invoice_id": str(invoice.id)},
    ))
    db.commit()
    return invoice


def get(db: Session, ctx: TenantContext, invoice_id: uuid.UUID) -> Invoice | None:
    return db.scalar(scoped(select(Invoice), Invoice, ctx).where(Invoice.id == invoice_id))


def get_issued(db: Session, ctx: TenantContext, invoice_id: uuid.UUID) -> Invoice:
    """The sanctioned way to fetch an invoice for issued-or-annulled,
    read-only use (the PDF endpoint) — an annulled invoice was validly
    issued and stays a real, historically-retained document (Wave 6 Issue
    30), so its PDF must remain retrievable exactly like any other issued
    invoice's. 404 if missing/wrong-tenant — `get()` already scopes that;
    409 if it's still a draft, so no "draft legal invoice" can ever be
    produced. Raises rather than returning `None` since every caller of
    this function has nothing useful left to do with a draft."""
    invoice = get(db, ctx, invoice_id)
    if invoice is None:
        raise InvoiceError("errors.invoices.not_found", status=404)
    if invoice.status not in ("issued", "annulled"):
        raise InvoiceError("errors.invoices.not_issued", status=409)
    return invoice


def list_invoices(db: Session, ctx: TenantContext, *, status: str | None = None,
                  order_id: uuid.UUID | None = None,
                  customer_id: uuid.UUID | None = None, limit: int = 50,
                  offset: int = 0) -> list[Invoice]:
    """Newest-first, paginated at the query level (never load-then-slice in
    Python) — the central invoice list's (GET /invoices) primary query.
    `Invoice.id` is a secondary sort key purely to make paging deterministic
    across requests when two rows share the same `created_at` (UUIDv7 ids are
    themselves time-ordered, so this never contradicts the primary key).

    `customer_id` (Issue 39; extended Wave 6 Issue 30 for manual invoices):
    matches BOTH an order-generated invoice whose order belongs to this
    customer (resolved via the sanctioned service_orders contract, never
    service_orders.models directly, then filtered on the IN-list) AND a
    manual invoice whose own `Invoice.customer_id` matches directly — one
    OR'd WHERE clause, still a single query, never N+1. Composes with
    `status` and pagination exactly like every other filter on this query."""
    stmt = scoped(select(Invoice), Invoice, ctx)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if order_id:
        stmt = stmt.where(Invoice.order_id == order_id)
    if customer_id:
        order_ids = orders_contracts.get_order_ids_for_customer(db, ctx, customer_id)
        stmt = stmt.where(
            or_(Invoice.order_id.in_(order_ids), Invoice.customer_id == customer_id)
        )
    stmt = stmt.order_by(Invoice.created_at.desc(), Invoice.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def draft_totals(db: Session, ctx: TenantContext,
                 invoice_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    """Batch counterpart to draft_total() — one query for a whole page of
    draft rows, not one per row (the central invoice list's list-friendly
    `total` field, commercial/router.py's list_invoices)."""
    ids = set(invoice_ids)
    if not ids:
        return {}
    totals: dict[uuid.UUID, Decimal] = dict.fromkeys(ids, Decimal("0"))
    rows = db.execute(
        scoped(select(InvoiceLine.invoice_id, InvoiceLine.qty, InvoiceLine.unit_price),
              InvoiceLine, ctx)
        .where(InvoiceLine.invoice_id.in_(ids))
    )
    for invoice_id, qty, unit_price in rows:
        totals[invoice_id] += qty * unit_price
    return totals


def list_lines(db: Session, ctx: TenantContext, invoice_id: uuid.UUID) -> list[InvoiceLine]:
    return list(db.scalars(
        scoped(select(InvoiceLine), InvoiceLine, ctx)
        .where(InvoiceLine.invoice_id == invoice_id)
        .order_by(InvoiceLine.sort)
    ))


def draft_total(db: Session, ctx: TenantContext, invoice_id: uuid.UUID) -> Decimal:
    """Informational only — never stored. The frozen net/vat/gross columns
    (docs/08) stay NULL until issue computes and freezes them; this is a
    live sum of the current lines, purely for the draft view."""
    return sum(
        (line.qty * line.unit_price for line in list_lines(db, ctx, invoice_id)),
        Decimal("0"),
    )


def replace_lines(db: Session, ctx: TenantContext, invoice: Invoice,
                  lines: list[dict[str, Any]]) -> Invoice:
    """Whole-document replace (docs/09 lists no separate invoice_lines
    endpoints, unlike part-lines/labor-lines) — draft only."""
    if invoice.status != "draft":
        raise InvoiceError("errors.invoices.not_draft")
    db.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id))
    for sort, fields in enumerate(lines):
        db.add(InvoiceLine(
            company_id=ctx.company_id, invoice_id=invoice.id,
            description=fields["description"], qty=fields["qty"],
            unit_price=fields["unit_price"], vat_rate=fields.get("vat_rate"),
            source=fields["source"], sort=sort,
        ))
    invoice.row_version += 1
    db.commit()
    return invoice


# --- Issue (non-VAT-registered seller only; buyer may be an individual or a
# domestic company, VAT-registered or not — docs/ACCOUNTANT_REVIEW.md
# 'RepairFlow Invoice V1 Freeze' §5 / §4 B1) --------------------------------


def _buyer_snapshot(customer: customers_contracts.CustomerSummary) -> dict[str, Any]:
    """Validates the buyer and builds the exact JSON to freeze into
    `Invoice.buyer`. Individual buyers are unchanged (`{"name": ...}`).
    Company buyers require name/address/ЕИК plus an explicitly-known
    `vat_registered` state (NULL is rejected, never silently treated as
    False): not VAT-registered buyers snapshot without a VAT number even if
    stale JSON left one behind; VAT-registered buyers require one, revalidated
    here rather than trusted from historical JSON (mirrors the seller-side
    EIK re-check above). The buyer's own VAT-registration status never
    affects the seller's VAT calculation — the seller is still non-VAT-
    registered, so vat_mode/vat/gross are unaffected by any of this."""
    if not customer.is_company:
        return {"name": customer.name}

    requisites = customer.company_requisites or {}
    address = requisites.get("address")
    eik_raw = requisites.get("eik")
    eik = normalize_eik(eik_raw) if eik_raw else None
    if not customer.name or not address or not eik or not is_valid_eik(eik):
        raise InvoiceError("errors.invoices.buyer_incomplete")

    if customer.vat_registered is None:
        raise InvoiceError("errors.invoices.buyer_vat_status_unknown")

    if customer.vat_registered is False:
        return {"name": customer.name, "address": address, "eik": eik, "vat_registered": False}

    vat_number_raw = requisites.get("vat_number")
    vat_number = normalize_vat_number(vat_number_raw) if vat_number_raw else None
    if not vat_number or not is_valid_vat_number(vat_number):
        raise InvoiceError("errors.invoices.buyer_vat_number_invalid")

    return {
        "name": customer.name, "address": address, "eik": eik,
        "vat_registered": True, "vat_number": vat_number,
    }


def issue(db: Session, ctx: TenantContext, invoice_id: uuid.UUID,
         tax_event_date: date) -> Invoice:
    """One transaction, one commit. Every validation that can fail runs
    before number allocation (`get_next_invoice_number` near the end), so
    the overwhelmingly common failure modes never touch the sequence at
    all — see the read-only Issue architectural audit this implements.

    Locks the Invoice row first (`SELECT ... FOR UPDATE`, via `scoped()`,
    so tenant isolation is inherited for free) — this is both the 404/
    not-found resolution and the concurrency mechanism: a second concurrent
    Issue call on the same invoice blocks here until the first commits or
    rolls back, then re-reads `status` (now `"issued"`) and rejects at the
    very next check, before ever reaching number allocation. Doing the fetch
    and the lock as one step (rather than the GET/PATCH endpoints' existing
    "router pre-fetches unlocked, then calls the service" shape) is a
    deliberate departure — Issue's exclusivity requirement is structurally
    different from a simple already-fetched-object mutation."""
    invoice = db.scalar(
        scoped(select(Invoice), Invoice, ctx)
        .where(Invoice.id == invoice_id)
        .with_for_update()
    )
    if invoice is None:
        raise InvoiceError("errors.invoices.not_found", status=404)
    if invoice.status != "draft":
        raise InvoiceError("errors.invoices.not_draft")

    lines = list_lines(db, ctx, invoice.id)
    if not lines:
        raise InvoiceError("errors.invoices.empty")
    # Defensive-only: qty>=1/unit_price>=0 are already enforced by
    # InvoiceLineIn at the only write path (replace_lines) — nothing here
    # can currently produce an invalid value, so there is no reachable
    # failure to reject, unlike the EIK re-check below (legacy/direct-DB
    # data can bypass request validation for a *stored* field; these are
    # ordinary ORM-typed int/Decimal columns, not free-form input).

    company = identity_contracts.get_company_profile(db, ctx.company_id)
    requisites = company.requisites or {}
    seller_address = requisites.get("address")
    seller_eik_raw = requisites.get("eik")
    seller_eik = normalize_eik(seller_eik_raw) if seller_eik_raw else None
    if not company.name or not seller_address or not seller_eik or not is_valid_eik(seller_eik):
        raise InvoiceError("errors.invoices.seller_incomplete")
    seller_vat_registered = company.vat_registered

    # Buyer-identity source forks on the Invoice model's XOR invariant
    # (Wave 6 Issue 30): order-generated invoices resolve through the
    # order's own customer, exactly as before; manual invoices resolve
    # directly through their own customer_id. Everything from here on
    # (VAT logic, totals, number allocation, freezing) is identical for
    # both — one issue() engine, not two.
    if invoice.order_id is not None:
        order = orders_contracts.get_order_summary(db, ctx, invoice.order_id)
        assert order is not None  # a real FK; scoped() already proved same-tenant
        customer = customers_contracts.get_customer_summary(db, ctx, order.customer_id)
        assert customer is not None  # same: a real FK, same-tenant by construction
    else:
        assert invoice.customer_id is not None  # XOR invariant: exactly one source is set
        customer = customers_contracts.get_customer_summary(db, ctx, invoice.customer_id)
        assert customer is not None  # same: a real FK, same-tenant by construction
    buyer_snapshot = _buyer_snapshot(customer)

    assert invoice.currency == "EUR"  # the only value any write path has ever set (server_default)

    # Buyer VAT status never affects this: the seller's own registration is
    # the only thing that determines whether VAT is charged at all. Only the
    # single standard rate is supported — a NULL (unset) or already-20.00
    # line is fine when the seller is registered; anything else means a
    # mixed/unsupported rate was set directly (never reachable through the
    # normal UI, which exposes no vat_rate input), so it is rejected exactly
    # like the non-VAT-registered path always rejected any non-NULL rate.
    if seller_vat_registered:
        if any(line.vat_rate not in (None, STANDARD_VAT_RATE) for line in lines):
            raise InvoiceError("errors.invoices.vat_state_invalid")
    else:
        if any(line.vat_rate is not None for line in lines):
            raise InvoiceError("errors.invoices.vat_state_invalid")

    net = sum((line.qty * line.unit_price for line in lines), Decimal("0"))
    if seller_vat_registered:
        # One rounding operation on the aggregate total, not per line then
        # summed (docs/ACCOUNTANT_REVIEW.md §6 — recorded there as an
        # implemented product decision pending professional confirmation).
        vat = (net * STANDARD_VAT_RATE / Decimal("100")).quantize(_CENT, rounding=ROUND_HALF_UP)
        gross = net + vat
        vat_mode = "registered"
        seller_vat_number = derive_seller_vat_number(seller_eik)
    else:
        vat = Decimal("0.00")
        gross = net
        vat_mode = "not_registered"
        seller_vat_number = None

    formatted_number = orders_contracts.get_next_invoice_number(db, ctx)

    # Freeze each line's own tax treatment alongside the invoice-level
    # totals — an issued line's vat_rate is Issue's output, not the draft's
    # input (mirrors how seller/buyer snapshots are independent JSON, never
    # references into live data).
    for line in lines:
        line.vat_rate = STANDARD_VAT_RATE if seller_vat_registered else None

    # Independent, immutable JSON values — never a reference into
    # Company.requisites/Customer.company_requisites, so a later edit to
    # either can never retroactively change an issued document.
    invoice.seller = {
        "name": company.name, "address": seller_address, "eik": seller_eik,
        "vat_registered": seller_vat_registered,
    }
    if seller_vat_registered:
        invoice.seller["vat_number"] = seller_vat_number
    invoice.buyer = buyer_snapshot
    invoice.vat_mode = vat_mode
    invoice.net = net
    invoice.vat = vat
    invoice.gross = gross
    invoice.number = int(formatted_number)
    invoice.issued_at = _now()
    invoice.tax_event_date = tax_event_date
    invoice.status = "issued"
    invoice.row_version += 1

    publish(db, DomainEvent(
        type="invoice_issued", company_id=ctx.company_id, actor_user_id=ctx.user_id,
        subject_id=invoice.order_id,
        data={"invoice_id": str(invoice.id), "invoice_number": formatted_number},
    ))
    db.commit()
    return invoice


# --- Annul (Wave 6 Issue 30; case-A documentation-error correction only,
# ЗДДС чл. 116 — see docs/ACCOUNTANT_REVIEW.md §7) --------------------------


def annul(db: Session, ctx: TenantContext, invoice_id: uuid.UUID, reason: str) -> Invoice:
    """Marks an already-issued invoice `status="annulled"`. Never edits,
    deletes, or renumbers it, never releases/reuses its number, never
    touches the frozen seller/buyer/lines/net/vat/gross, never populates
    `annuls_invoice_id` (reserved for a future reissue-linkage feature, not
    this flow), and never touches any Payment — annulment is a pure
    status+metadata transition, irreversible once committed (no code path
    anywhere transitions status away from "annulled").

    Locks the row first, same as `issue()`, so a concurrent annul (or a
    concurrent issue racing an annul of a *different* invoice) serializes
    on the same row-lock mechanism rather than needing a second scheme."""
    invoice = db.scalar(
        scoped(select(Invoice), Invoice, ctx)
        .where(Invoice.id == invoice_id)
        .with_for_update()
    )
    if invoice is None:
        raise InvoiceError("errors.invoices.not_found", status=404)
    if invoice.status == "draft":
        raise InvoiceError("errors.invoices.annul_not_issued")
    if invoice.status == "annulled":
        raise InvoiceError("errors.invoices.already_annulled")

    invoice.annul_reason = reason
    invoice.annulled_at = _now()
    invoice.status = "annulled"
    invoice.row_version += 1

    publish(db, DomainEvent(
        type="invoice_annulled", company_id=ctx.company_id, actor_user_id=ctx.user_id,
        subject_id=invoice.order_id,
        data={"invoice_id": str(invoice.id), "reason": reason},
    ))
    db.commit()
    return invoice
