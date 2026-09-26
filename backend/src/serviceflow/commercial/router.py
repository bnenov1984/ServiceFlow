"""Commercial endpoints per docs/09 §Commercial documents.

Payment is deliberately outside the ServiceOrder aggregate (docs/01 §4, same
category as Task/Attachment/ContactRecord) — service_orders/router.py's
OrderDetailOut carries only the derived paid_amount/balance summary, not a raw
payments list, matching how Task/Attachment/ContactRecord are exposed via
their own endpoints rather than embedded.

Invoice is a Draft-then-Issue-then-PDF slice here: POST /orders/{id}/invoices
creates an order-generated draft prefilled from the order's lines (via
service_orders' public contract — never its internal models); POST /invoices
(Wave 6 Issue 30) creates a manual, order-less draft from a directly-supplied
`customer_id` instead — same Invoice row shape, same draft/issue/PDF/annul
machinery downstream, see commercial/service.py's `create_manual_draft()`.
GET lists/reads, PATCH replaces the line set
(drafts only, docs/09 lists no separate invoice_lines sub-resource, unlike
part-lines/labor-lines), POST .../issue transitions draft -> issued
(non-VAT-registered seller only; buyer may be an individual or a domestic
company, VAT-registered or not — see commercial/service.py's `issue()`),
POST .../annul transitions issued -> annulled (Wave 6 Issue 30, case-A
documentation-error correction only — see commercial/service.py's
`annul()`; never edits/renumbers/deletes, no reissue-linkage in V1), GET
.../invoice.pdf renders the issued-or-annulled document (same buyer
coverage; see commercial/pdf.py). No reissue endpoint and no `?q=` search
yet (see commercial/models.py's module docstring).

GET /invoices doubles as the central invoice list (frontend's /invoices
workspace, docs/01 §Invoice): `InvoiceListItemOut` enriches each row with
order_number/customer_name/total via bounded batch lookups
(service_orders.contracts.get_order_summaries,
customers.contracts.get_customer_summaries, commercial.service.draft_totals)
— never one query per row. customer_name is intentionally dual-sourced: an
issued row's buyer identity is the invoice's own frozen `buyer` snapshot
(never live Customer data, even if malformed — docs/ACCOUNTANT_REVIEW.md);
a draft row has no snapshot yet, so it falls back to the live Customer name
via its order (or, for a manual invoice, its own `customer_id` directly —
Wave 6 Issue 30). `total` is the frozen `gross` once an invoice carries one
(issued, and any future annulled row), otherwise the live sum of its current
lines (draft) — one field, not two, but never a Draft total presented as a
legal one."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator

from business_os.identity.deps import (
    TenantDbDep,
    TenantDep,
    require_csrf,
    require_owner,
    require_repairflow_active,
    require_subscription_ok,
)
from serviceflow.commercial import pdf as invoice_pdf
from serviceflow.commercial import service
from serviceflow.commercial.models import Invoice, InvoiceLine, Payment
from serviceflow.customers import contracts as customers_contracts
from serviceflow.service_orders import contracts as orders_contracts

router = APIRouter(dependencies=[Depends(require_repairflow_active)])


class PaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str = Field(pattern="^(cash|card|bank)$")
    is_refund: bool = False
    note: str = Field(default="", max_length=1000)


class PaymentOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    invoice_id: uuid.UUID | None
    amount: float
    method: str
    is_refund: bool
    note: str
    received_by: uuid.UUID
    received_at: datetime

    @staticmethod
    def of(p: Payment) -> "PaymentOut":
        return PaymentOut(
            id=p.id, order_id=p.order_id, invoice_id=p.invoice_id, amount=float(p.amount),
            method=p.method, is_refund=p.is_refund, note=p.note, received_by=p.received_by,
            received_at=p.received_at,
        )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "code": "not_found", "message_key": "errors.orders.not_found", "params": {},
    })


@router.post("/orders/{order_id}/payments",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
             status_code=201)
def add_payment(order_id: uuid.UUID, body: PaymentIn, db: TenantDbDep,
                tenant: TenantDep) -> PaymentOut:
    order = orders_contracts.get_order_summary(db, tenant, order_id)
    if order is None:
        raise _not_found()
    # Terminal orders still accept payments settling an outstanding balance
    # (docs/01 §ServiceOrder invariants) — only archiving closes the door.
    if order.archived:
        raise HTTPException(status_code=409, detail={
            "code": "order_error", "message_key": "errors.orders.archived", "params": {},
        })
    payment = service.add_payment(
        db, tenant, order.id, amount=body.amount, method=body.method,
        is_refund=body.is_refund, note=body.note,
    )
    return PaymentOut.of(payment)


# --- Invoice drafts (docs/01 §Invoice) --------------------------------------

class InvoiceLineIn(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    qty: int = Field(default=1, ge=1)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    vat_rate: Decimal | None = Field(default=None, ge=0)
    source: str = Field(pattern="^(labor|part|manual|adjustment)$")


class InvoiceLineOut(BaseModel):
    id: uuid.UUID
    description: str
    qty: int
    unit_price: float
    vat_rate: float | None
    source: str

    @staticmethod
    def of(line: InvoiceLine) -> "InvoiceLineOut":
        return InvoiceLineOut(
            id=line.id, description=line.description, qty=line.qty,
            unit_price=float(line.unit_price),
            vat_rate=float(line.vat_rate) if line.vat_rate is not None else None,
            source=line.source,
        )


class InvoicePatchIn(BaseModel):
    lines: list[InvoiceLineIn]


class InvoiceOut(BaseModel):
    id: uuid.UUID
    # Wave 6 Issue 30 — NULL for a manual invoice (no ServiceOrder). Exactly
    # one of order_id/customer_id is ever set; see the Invoice model's XOR
    # invariant docstring.
    order_id: uuid.UUID | None
    customer_id: uuid.UUID | None
    status: str
    number: int | None
    currency: str
    row_version: int

    @staticmethod
    def of(invoice: Invoice) -> "InvoiceOut":
        return InvoiceOut(
            id=invoice.id, order_id=invoice.order_id, customer_id=invoice.customer_id,
            status=invoice.status, number=invoice.number, currency=invoice.currency,
            row_version=invoice.row_version,
        )


class InvoiceDetailOut(InvoiceOut):
    lines: list[InvoiceLineOut]
    # Informational sum of current lines (BR-3, never stored). Kept in the
    # response unconditionally rather than branching the schema by status:
    # once issued, lines are frozen, so this is always numerically identical
    # to `net` (both = Σ qty×unit_price) — `net`/`vat`/`gross` below are the
    # authoritative, immutable legal totals; this is a live/informational
    # echo that happens to agree with them post-Issue.
    draft_total: float
    # Taxable-event date (ЗДДС чл. 114, ал. 1; docs/ACCOUNTANT_REVIEW.md §2) —
    # distinct from issued_at. NULL for every Draft; populated by Issue.
    tax_event_date: date | None
    # Issue-owned fields (docs/ACCOUNTANT_REVIEW.md 'RepairFlow Invoice V1
    # Freeze' §5, Phase-A) — NULL for every Draft, populated atomically by
    # POST .../issue. No request schema in this file accepts any of these;
    # they are exclusively server-written.
    issued_at: datetime | None
    seller: dict[str, Any] | None
    buyer: dict[str, Any] | None
    vat_mode: str | None
    net: float | None
    vat: float | None
    gross: float | None
    # Wave 6 Issue 30 — NULL unless annul() has transitioned this invoice to
    # "annulled"; never set alongside seller/buyer/net/vat/gross above,
    # which stay exactly as Issue froze them.
    annulled_at: datetime | None
    annul_reason: str | None


def _invoice_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "code": "not_found", "message_key": "errors.invoices.not_found", "params": {},
    })


def _invoice_error(e: service.InvoiceError) -> HTTPException:
    # 404s raised as InvoiceError (Issue's locked-fetch-not-found path) get
    # the exact same envelope shape _invoice_not_found() already uses for
    # every other endpoint's not-found case — one 404 shape, not two.
    code = "not_found" if e.status == 404 else "invoice_error"
    return HTTPException(status_code=e.status, detail={
        "code": code, "message_key": e.message_key, "params": {},
    })


def _invoice_detail(db: TenantDbDep, tenant: TenantDep, invoice: Invoice) -> InvoiceDetailOut:
    return InvoiceDetailOut(
        **InvoiceOut.of(invoice).model_dump(),
        lines=[InvoiceLineOut.of(line) for line in service.list_lines(db, tenant, invoice.id)],
        draft_total=float(service.draft_total(db, tenant, invoice.id)),
        tax_event_date=invoice.tax_event_date,
        issued_at=invoice.issued_at,
        seller=invoice.seller,
        buyer=invoice.buyer,
        vat_mode=invoice.vat_mode,
        net=float(invoice.net) if invoice.net is not None else None,
        vat=float(invoice.vat) if invoice.vat is not None else None,
        gross=float(invoice.gross) if invoice.gross is not None else None,
        annulled_at=invoice.annulled_at,
        annul_reason=invoice.annul_reason,
    )


@router.post("/orders/{order_id}/invoices",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
             status_code=201)
def create_invoice_draft(order_id: uuid.UUID, db: TenantDbDep,
                         tenant: TenantDep) -> InvoiceDetailOut:
    order = orders_contracts.get_order_summary(db, tenant, order_id)
    if order is None:
        raise _not_found()
    if order.archived:
        raise HTTPException(status_code=409, detail={
            "code": "order_error", "message_key": "errors.orders.archived", "params": {},
        })
    invoice = service.create_draft(db, tenant, order.id)
    return _invoice_detail(db, tenant, invoice)


class ManualInvoiceIn(BaseModel):
    customer_id: uuid.UUID


@router.post(
    "/invoices",
    dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
    status_code=201,
)
def create_manual_invoice_draft(body: ManualInvoiceIn, db: TenantDbDep,
                                tenant: TenantDep) -> InvoiceDetailOut:
    """Wave 6 Issue 30: the manual counterpart to `POST /orders/{id}/invoices`
    — same permission posture (Worker may create drafts; only Issue/Annul are
    Owner-only), same draft/replace-lines/issue/PDF/annul machinery
    downstream, only the buyer-identity source and the empty starting line
    set differ. Kept as its own top-level route (not a sub-resource of
    anything) since a manual invoice has no parent resource to nest under."""
    try:
        invoice = service.create_manual_draft(db, tenant, body.customer_id)
    except service.InvoiceError as e:
        raise _invoice_error(e) from e
    return _invoice_detail(db, tenant, invoice)


class InvoiceListItemOut(BaseModel):
    id: uuid.UUID
    # Wave 6 Issue 30 — both NULL for a manual invoice (no ServiceOrder);
    # the frontend renders "—" in the order column for those rows.
    order_id: uuid.UUID | None
    # Human order number (e.g. "2026-00001"), not this endpoint's own concern
    # to compute — sourced via service_orders.contracts.get_order_summaries.
    order_number: str | None
    status: str
    number: int | None
    currency: str
    # Dual-sourced by design — see this module's docstring for the full
    # rationale: frozen Invoice.buyer snapshot once issued, live Customer
    # name while still a draft. Never both, never guessed.
    customer_name: str
    issued_at: datetime | None
    tax_event_date: date | None
    # Frozen `gross` once the invoice carries one (issued, or any future
    # annulled row); otherwise the live sum of the draft's current lines.
    # One field, not a redundant issued/draft pair — see module docstring.
    total: float
    row_version: int


def _customer_name_for(
    invoice: Invoice,
    orders: dict[uuid.UUID, orders_contracts.OrderSummary],
    customers: dict[uuid.UUID, customers_contracts.CustomerSummary],
) -> str:
    if invoice.buyer is not None:
        # Frozen legal snapshot (Issue-time) — never live Customer data, even
        # for a legacy/malformed snapshot missing "name" (falls back to "",
        # the same "missing enrichment data" convention list_orders already
        # uses, rather than reaching for live Customer to paper over it).
        return str(invoice.buyer.get("name") or "")
    if invoice.order_id is not None:
        order = orders.get(invoice.order_id)
        customer = customers.get(order.customer_id) if order else None
        return customer.name if customer else ""
    # Manual draft (Wave 6 Issue 30) — no order to resolve through; its own
    # customer_id is the direct source.
    customer = customers.get(invoice.customer_id) if invoice.customer_id else None
    return customer.name if customer else ""


@router.get("/invoices")
def list_invoices(
    db: TenantDbDep, tenant: TenantDep, status: str | None = None,
    order_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(gt=0, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[InvoiceListItemOut]:
    invoices = service.list_invoices(
        db, tenant, status=status, order_id=order_id, customer_id=customer_id,
        limit=limit, offset=offset,
    )
    orders = orders_contracts.get_order_summaries(
        db, tenant, (i.order_id for i in invoices if i.order_id is not None),
    )
    # Only Draft rows ever need a live customer lookup — issued rows resolve
    # customer_name entirely from their own frozen buyer snapshot, above.
    # Covers both an order-generated draft's order.customer_id and a manual
    # draft's own customer_id (Wave 6 Issue 30) — one batch fetch, not two.
    draft_customer_ids = {
        orders[i.order_id].customer_id for i in invoices
        if i.buyer is None and i.order_id is not None and i.order_id in orders
    } | {
        i.customer_id for i in invoices
        if i.buyer is None and i.order_id is None and i.customer_id is not None
    }
    customers = customers_contracts.get_customer_summaries(db, tenant, draft_customer_ids)
    totals = service.draft_totals(db, tenant, (i.id for i in invoices if i.gross is None))
    return [
        InvoiceListItemOut(
            id=i.id, order_id=i.order_id,
            order_number=(
                orders[i.order_id].number if i.order_id is not None and i.order_id in orders
                else None
            ),
            status=i.status, number=i.number, currency=i.currency,
            customer_name=_customer_name_for(i, orders, customers),
            issued_at=i.issued_at, tax_event_date=i.tax_event_date,
            total=float(i.gross) if i.gross is not None else float(totals.get(i.id, Decimal("0"))),
            row_version=i.row_version,
        )
        for i in invoices
    ]


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> InvoiceDetailOut:
    invoice = service.get(db, tenant, invoice_id)
    if invoice is None:
        raise _invoice_not_found()
    return _invoice_detail(db, tenant, invoice)


@router.patch("/invoices/{invoice_id}",
             dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def patch_invoice(invoice_id: uuid.UUID, body: InvoicePatchIn, db: TenantDbDep,
                  tenant: TenantDep) -> InvoiceDetailOut:
    invoice = service.get(db, tenant, invoice_id)
    if invoice is None:
        raise _invoice_not_found()
    fields: list[dict[str, Any]] = [line.model_dump() for line in body.lines]
    try:
        invoice = service.replace_lines(db, tenant, invoice, fields)
    except service.InvoiceError as e:
        raise _invoice_error(e) from e
    return _invoice_detail(db, tenant, invoice)


class LinkOrderRequest(BaseModel):
    order_id: uuid.UUID


@router.post(
    "/invoices/{invoice_id}/link-order",
    dependencies=[Depends(require_csrf), Depends(require_subscription_ok)],
)
def link_invoice_to_order(invoice_id: uuid.UUID, body: LinkOrderRequest, db: TenantDbDep,
                          tenant: TenantDep) -> InvoiceDetailOut:
    """invoice-order-linking checkpoint 1. Same permission tier as
    patch_invoice/create_manual_invoice_draft — sets a reference, not a
    legally significant transition, so no require_owner."""
    try:
        invoice = service.link_to_order(db, tenant, invoice_id, body.order_id)
    except service.InvoiceError as e:
        raise _invoice_error(e) from e
    return _invoice_detail(db, tenant, invoice)


class IssueRequest(BaseModel):
    # The only client-owned datum Issue accepts — number/seller/buyer/
    # totals/vat_mode/issued_at/status are exclusively server-resolved
    # (docs/ACCOUNTANT_REVIEW.md D1: never backend-derived, so no default
    # here either — omitting it is a validation failure, not an auto-fill).
    tax_event_date: date


@router.post(
    "/invoices/{invoice_id}/issue",
    dependencies=[Depends(require_csrf), Depends(require_owner), Depends(require_subscription_ok)],
)
def issue_invoice(invoice_id: uuid.UUID, body: IssueRequest, db: TenantDbDep,
                  tenant: TenantDep) -> InvoiceDetailOut:
    try:
        invoice = service.issue(db, tenant, invoice_id, body.tax_event_date)
    except service.InvoiceError as e:
        raise _invoice_error(e) from e
    return _invoice_detail(db, tenant, invoice)


class AnnulRequest(BaseModel):
    # Required and non-blank (Wave 6 Issue 30) — a mistake-only correction
    # mechanism (ЗДДС чл. 116, case A), never a silent/reasonless cancel.
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("blank reason")
        return stripped


@router.post(
    "/invoices/{invoice_id}/annul",
    dependencies=[Depends(require_csrf), Depends(require_owner), Depends(require_subscription_ok)],
)
def annul_invoice(invoice_id: uuid.UUID, body: AnnulRequest, db: TenantDbDep,
                  tenant: TenantDep) -> InvoiceDetailOut:
    try:
        invoice = service.annul(db, tenant, invoice_id, body.reason)
    except service.InvoiceError as e:
        raise _invoice_error(e) from e
    return _invoice_detail(db, tenant, invoice)


@router.get(
    "/invoices/{invoice_id}/invoice.pdf",
    # FastAPI can't infer a binary media type from -> Response alone (it
    # would otherwise document 200 as application/json, wrong for every
    # byte of this response) — the sibling /orders/{id}/protocol.pdf
    # predates this annotation and still has that stale declaration; not
    # fixed here since it's a separate, already-shipped endpoint.
    responses={200: {"content": {"application/pdf": {}}}},
)
def get_invoice_pdf(invoice_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> Response:
    """Read-only: no mutation, no number allocation, no timeline event, no
    commit — generated fresh from the frozen Invoice/InvoiceLine snapshot on
    every request (see commercial/pdf.py's module docstring). Route path
    matches docs/09_API_SPECIFICATION.md's frozen surface and the sibling
    `/orders/{id}/protocol.pdf` naming convention, not a bare `/pdf`."""
    try:
        invoice = service.get_issued(db, tenant, invoice_id)
    except service.InvoiceError as e:
        raise _invoice_error(e) from e
    lines = service.list_lines(db, tenant, invoice.id)
    pdf_bytes = invoice_pdf.generate_invoice_pdf(invoice_pdf.to_pdf_data(invoice, lines))
    assert invoice.number is not None  # guaranteed by get_issued()'s status=="issued" check
    filename = f"invoice-{invoice.number:010d}.pdf"
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
