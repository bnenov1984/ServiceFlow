# Attach an existing manual invoice to a service order

Status: done (2026-09-26) — backend (checkpoint 1) and frontend order-picker
action (checkpoint 2) both shipped.

## Implementation notes (checkpoint 1 — backend)

XOR invariant confirmed application-code only, no DB CHECK constraint
(migration `0029`'s own docstring) — no migration needed. Added
`commercial.service.link_to_order()` + `POST /invoices/{invoice_id}/
link-order` (same permission tier as `patch_invoice`/
`create_manual_invoice_draft`: `require_csrf` + `require_subscription_ok`,
no `require_owner` — sets a reference, not a legally significant
transition). Validates, in order: invoice exists (404), invoice not
already linked (`errors.invoices.already_linked` — also correctly rejects
re-linking and linking an order-generated invoice, since both already
carry a non-null `order_id`), order exists in-tenant (404,
`errors.orders.not_found`), order not archived (`errors.orders.archived`,
matching `create_invoice_draft`'s existing check), order's customer
matches the invoice's `customer_id` (`errors.invoices.customer_mismatch`
— hard rule, per the scope's own recommendation). Emits `invoice_linked`
on the order's timeline — required adding it to `timeline.service.
KNOWN_EVENT_TYPES`, an easy-to-miss step since an unlisted event type is
silently dropped by the subscriber, not rejected.

`customer_id` is deliberately left set after linking, not cleared — traced
every `order_id is None`/`is not None` fork in `commercial/` first (per
this ticket's own instruction): `issue()`'s buyer-resolution fork only
matters pre-issue, and `_customer_name_for()` checks the frozen `buyer`
snapshot before ever looking at `order_id`, so a post-issue link never
retroactively changes the resolved buyer. Confirmed by test: linking an
already-issued manual invoice leaves its frozen `gross` unchanged. The
Invoice model's "exactly one of order_id/customer_id" XOR docstring is
therefore slightly imprecise for a linked row — describes construction,
not an ongoing invariant this function re-establishes; worth a docstring
note if that model is touched again.

No frontend change was needed for linked invoices to appear in the
order's own invoice section — `InvoiceCard.tsx`/`OrderPage.tsx` already
query `GET /invoices?order_id=`, so setting `order_id` server-side is
sufficient on next fetch.

New test file `backend/tests/test_invoice_order_linking.py` (14 tests):
success (draft and already-issued invoice), row_version bump, appears in
order's invoice list, timeline event recorded, every rejection path above,
cross-tenant order treated as not-found, Worker permission (not owner-
only), missing-CSRF.

Verified: full backend suite 788 passed/2 xfailed (774 prior + 14 new,
same known fpdf xfails), frontend 523/523, `tsc --noEmit`/`ruff`/`mypy`/
`lint-imports` all clean. `frontend/src/i18n/bg.ts` got two new keys
(`errors.invoices.already_linked`, `errors.invoices.customer_mismatch`);
`errors.orders.not_found`/`errors.orders.archived` were reused as-is.
OpenAPI contract (`frontend/src/generated/{openapi.json,api.d.ts}`)
regenerated.

## Implementation notes (checkpoint 2 — frontend)

New `frontend/src/invoices/LinkOrderDialog.tsx`, rendered from
`InvoiceDetailPage.tsx`'s existing `invoice.order_id !== null` branch point
(the sibling `=== null` case now shows a "Свържи с поръчка" button instead
of nothing). Lists the invoice's own customer's orders split into
active/history, deliberately as two explicit `GET /orders?state=open` +
`GET /orders?state=terminal` fetches (reusing the exact
`queryKeys.customerOrders` cache `CustomerOrdersSection` already populates
on the customer profile page) rather than relying on `list_orders`'s
`state` param falling through to "all orders" for any unrecognized string —
traced that fallthrough in `service_orders/service.py` and confirmed it has
zero test coverage, so it isn't a contract worth building on.

Clicking an order links immediately, no secondary confirm dialog — matches
this endpoint's own permission tier (no `require_owner`, "not a legally
significant transition"). On success: the invoice cache is seeded directly
from the response (same pattern as `InvoiceDraftEditor`'s `submitIssue`),
plus the linked order's `orderInvoices`/`orderTimeline` cache entries are
invalidated (genuinely server-derived, not locally fabricable — same
reasoning `submitIssue` already uses for its own equivalent step).

New i18n: `invoice.link_to_order_action`, `invoice.link_to_order_title`,
`invoice.linked_to_order_success`; the two picker sections reuse the
existing `customer.active_orders`/`customer.active_orders_none`/
`customer.history`/`customer.history_none` keys rather than duplicating
the wording.

**Real bug caught in manual browser QA** (seeded a fresh company, created a
customer/order/manual invoice, and drove the full flow end-to-end): the
order's own timeline rendered the just-added `invoice_linked` event as the
raw event-type string, not Bulgarian text — checkpoint 1 added it to the
backend's `KNOWN_EVENT_TYPES` allowlist but never to
`frontend/src/order/TimelineSection.tsx`'s separate `EVENT_LABEL` display
map, which silently falls back to the raw type for anything unmapped.
Fixed: added the mapping + `order.event_invoice_linked` key ("Фактурата е
свързана с поръчката", no trailing period, matching every sibling event
label's convention) + a regression test in `TimelineSection.test.tsx`.

Also surfaced and fixed in passing: the harness's ambient shell environment
carries a `SERVICEFLOW_DATABASE_URL` pointing at a Neon cloud Postgres
instance, silently overriding `backend/.env`'s local Docker URL for any
process that inherits it (pydantic-settings env vars win over `.env`) —
including a `preview_start`-launched backend dev server. Worked around by
starting the backend manually with the URL pinned inline instead of via
the `backend` launch-config entry; worth the user's own attention since
it's not a ServiceFlow-repo artifact and isn't mentioned anywhere in
`CLAUDE.md`.

Verified: full frontend suite 529/529 (523 prior + 5 new
`InvoiceDetailPage.test.tsx` cases + 1 new `TimelineSection.test.tsx`
case), `tsc --noEmit` clean, `npm run build` clean. Backend untouched this
checkpoint, so its own suite wasn't re-run. Manually driven end-to-end
against real dev servers (seeded company → new customer/order/manual
invoice → link → order page shows both the invoice and the corrected
timeline entry).

## Context

See `../spec.md`. `create_manual_draft()` (`commercial/service.py:133`)
issues an invoice with `order_id=None`. This ticket adds a way to set
`order_id` on such an invoice later.

## Scope

- Check the `order_id`/`customer_id` XOR invariant's enforcement point
  (DB CHECK constraint vs Pydantic/service validation) before changing
  anything — this determines whether linking requires a migration.
- New endpoint, e.g. `POST /invoices/{invoice_id}/link-order` — validates:
  - Invoice currently has `order_id IS NULL` (only unlinked manual invoices
    can be linked; don't allow re-linking or linking an order-issued
    invoice).
  - The order's customer matches the invoice's `customer_id` (don't allow
    linking to an unrelated customer's order — decide whether this is a
    hard rule or a warning; hard rule is safer and matches the rest of this
    codebase's validation strictness).
  - Issued invoices remain immutable in their financial content (root
    `CLAUDE.md` rule 6) — linking sets a reference (`order_id`), not
    totals/lines, so this doesn't violate immutability, but confirm no
    other code path assumes `order_id IS NULL` implies "manual invoice" in
    a way that would break once linked (search for `order_id is None`/
    `order_id == None` across `commercial/`).
  - Emits a timeline event on the linked order (append-only timeline, root
    `CLAUDE.md` rule 6) so the link is visible in the order's history.
- Frontend: an "Свържи с поръчка" action on the standalone invoice detail
  page (`frontend/src/invoices/` — check current structure, likely near
  `a7fdb33`'s standalone invoice detail page), with an order picker scoped
  to the invoice's customer. Also surface linked manual invoices in
  `OrderPage.tsx`'s invoice section once linked.

## Acceptance criteria

- New backend tests: successful link, reject-if-already-linked,
  reject-if-customer-mismatch, timeline event recorded.
- `uv run pytest`, `lint-imports`, `tsc --noEmit` clean.
