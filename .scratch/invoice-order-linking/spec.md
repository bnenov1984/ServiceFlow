# Link a manual invoice to an order after the fact

## Source

Wave 6 audit item **30**, second half. First half (annulment + manual
invoice creation) is already implemented (commits `31d20e4`, `6d16760`) and
confirmed working. This spec covers only the missing "последващо
свързване" (subsequent linking) part.

## Important distinction from the existing `annuls_invoice_id` field

`commercial/models.py`'s `annuls_invoice_id` is a **different** feature —
reserved (per its own docstring, unused in V1) for invoice-reissue linkage
(annul invoice A, issue invoice B that supersedes it). **Do not repurpose
it for this.** What's needed here is linking a manual invoice (created with
`order_id=None`) to a `ServiceOrder` after the invoice already exists —
a new relationship, not the reissue one.

## PO decision (2026-09-25)

In scope now (PO explicitly asked to add this, not defer it).

## Current state

`commercial/service.py`'s `create_manual_draft()` creates an invoice with
`order_id=None`, `customer_id` set (XOR invariant with `order_id` — check
whether that XOR is a DB constraint or just service-layer logic before
changing it, since this feature requires `order_id` to become settable
post-creation while `customer_id` presumably stays).

## Issues

1. [01-attach-manual-invoice-to-order.md](issues/01-attach-manual-invoice-to-order.md)
