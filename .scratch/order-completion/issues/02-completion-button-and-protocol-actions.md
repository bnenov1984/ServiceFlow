# "Приключи поръчката" button + post-completion action menu

Status: done (2026-09-25) — scope narrowed, see notes

## Implementation notes

Landed: the dedicated primary button (only on a `ready`, non-archived
order), `runDelivery` → `runComplete`, `DeliveryDialog.tsx` →
`dialogs/CompletionDialog.tsx` (component, props, all `order.delivery_*`
i18n keys → `order.completion_*`, confirm button "Предай" → "Приключи"),
the `PendingAction` discriminator `"delivery"` → `"completion"` in both
`OrderHeader.tsx` and the Kanban-board equivalent
(`orders/OrderStatusActions.tsx`, which shares the same dialog and got the
same rename). "completed" is now excluded from the generic "Промени
статус" dropdown everywhere (`requestTransition`'s dead `to === "completed"`
branch removed) — the dedicated button is the only way to reach it from
the order detail page; Kanban drag-and-drop to the "Приключена" column is
untouched (still opens the same dialog, just via its own path).

Updated the two E2E specs that drove this through the old dropdown+
"Предай" path (`order-delivery.spec.ts`, `order-invoice.spec.ts`) and
`frontend/e2e/CLAUDE.md`'s description of them, plus 5 stray doc comments
elsewhere that named `DeliveryDialog` by name (`AppShell.tsx`,
`AuthContext.tsx`, `CompanyRequisitesPage.tsx`, `test-setup.ts`,
`AccessoriesListSection.tsx`). Added 6 new `OrderHeader.test.tsx` cases:
button visibility (ready-only, hidden when archived), dropdown exclusion,
dialog open, and the `to: "completed"` submit.

**Scope narrowed from the original spec**: the "post-completion three-action
menu" (print / email protocol / email protocol+warranty) is NOT built here.
Two of those three actions need issue 03's email backend endpoint, which
doesn't exist yet — per this repo's own "no half-finished implementations"
rule, building a menu with two dead buttons pending a future issue would be
worse than deferring the whole menu to issue 03, where it can land complete
and wired end to end. Today's existing "Протокол за предаване" print
button is untouched (still visible on a `terminal_success` order, same
`?type=delivery` param — issue 03's territory, per issue 01's scope note).

Verified: frontend 512 passed (up from 506), `tsc --noEmit` clean. No
backend files touched this issue. E2E specs updated by inspection only —
not run live (no dev/E2E stack started this session).

## Context

Today, `frontend/src/order/OrderHeader.tsx` drives `ready -> delivered` via
a delivery action that opens `frontend/src/order/dialogs/DeliveryDialog.tsx`
(payment method, warranty days, etc.), per commit `d02e051`'s
operation-token-guarded `runDelivery`.

PO wants this reframed as completion, not delivery:

- On a `ready` order, the primary action button reads **"Приключи
  поръчката"**.
- Confirming it runs the (now-renamed, see issue 01) `ready -> completed`
  transition — same dialog fields (payment, warranty) can stay, this is a
  relabel + the status-code rename, not a new business flow.
- After the order is `completed`, present three actions instead of (or
  alongside) the current print-only protocol button:
  1. Print protocol (existing, `service_orders/protocol.py`)
  2. Email protocol (new — see issue 03)
  3. Email protocol + warranty (new — see issue 03; likely the same email
     with an additional warranty section/attachment)

## Scope

- Rename `runDelivery` → `runComplete` (or similar) in `OrderHeader.tsx`,
  preserving the operation-token guard pattern from `d02e051` (do not
  reintroduce the stale-dialog-clobbering race it fixed).
- Rename `DeliveryDialog.tsx` → `CompletionDialog.tsx` (or keep filename,
  rename displayed copy — repo convention seems to tolerate either; prefer
  renaming the component for AI-navigability per this repo's `codebase-design`
  usage elsewhere).
- Add the post-completion three-action menu/section to the order page
  (`frontend/src/order/OrderPage.tsx` or wherever the current print-protocol
  button lives).
- Update `frontend/src/i18n/bg.ts` with the new button/menu copy (no literal
  strings in components, per root `CLAUDE.md` rule 4).

## Acceptance criteria

- Frontend vitest + `tsc --noEmit` clean.
- New/updated component test coverage for the renamed button and the
  post-completion action menu (three actions render, print still works
  unchanged).
- E2E: update `order-delivery.spec.ts` (rename to `order-completion.spec.ts`
  per `frontend/e2e/CLAUDE.md`'s growth rules if it's being substantially
  rewritten) to assert the new button label and the three post-completion
  actions.
