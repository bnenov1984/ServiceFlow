# Rename terminal status `delivered` → `completed` ("Предадена" → "Приключена")

Status: done (2026-09-25)

## Implementation notes

Landed as migration `0031_rename_delivered_to_completed.py` (reassign-then-
drop, same pattern as `0021`) plus a column rename `delivered_at` →
`completed_at`, the `order_delivered` → `order_completed` timeline event
(old event type kept mapped for historical rows, per BR-5), and the
`errors.orders.warranty_needs_delivered` → `..._needs_completed` message
key. Full surface: `statuses.py`, `service.py`, `router.py`'s `OrderOut`,
`protocol.py`'s one-line snapshot-key read, `timeline/service.py`'s
allowlist, `frontend/src/i18n/bg.ts`, `TimelineSection.tsx`,
`OrderHeader.tsx`, `OrderStatusActions.tsx`, `OrderPage.tsx`,
`InvoiceCard.tsx`/`.test.tsx`, `InvoiceDraftEditor.tsx`,
`InvoiceDetailPage.tsx`/`.test.tsx`, both `order-delivery.spec.ts`/
`order-invoice.spec.ts` E2E specs (text-only; not run live this session).

Deliberately NOT touched here (left for issue 02/03, where they belong):
`DeliveryDialog.tsx`'s filename/component, `runDelivery`'s name, the
"Протокол за предаване" PDF title/labels, the `?type=delivery` query param,
`DeliveryProtocolData`'s field names. The order can now transition through
its full lifecycle correctly under the new status code — the UX/copy layer
on top of it is what issues 02/03 rework.

Verified: backend 753 passed + 1 xfail (4 new migration regression tests),
frontend 506 passed, `tsc --noEmit`/`ruff`/`mypy`/`lint-imports` all clean.
Not verified: live Playwright E2E run (Docker/dev-server E2E stack not
started this session — the two spec files were updated by inspection only).

## Context

`backend/src/serviceflow/service_orders/statuses.py` `STATUSES` dict has
`"delivered": (Kind.TERMINAL_SUCCESS, "Предадена", 8)`. This is a real DB-FK'd
row in `order_statuses` (seeded), referenced by `service_orders.status_code`
on every delivered order, and hardcoded in the transition matrix `_M`,
frontend status labels, i18n keys, and E2E tests
(`frontend/e2e/repairflow/order-delivery.spec.ts`,
`order-invoice.spec.ts`).

Follow the pattern from migration `0021` (testing → repair fold): a forward
migration must reassign existing rows before the old code can be dropped —
this is not a pure rename at the DB level if `order_statuses.code` is a
primary/foreign key elsewhere.

## Scope

- New migration: update the `order_statuses` seed row's `code` from
  `delivered` to `completed` and `name_bg` to `Приключена` (or insert new +
  reassign + drop old, matching the `0021` pattern — check whether `code` is
  referenced by FK in a way that allows a simple `UPDATE` vs requiring
  reassignment).
- `statuses.py`: rename the `STATUSES` key and update all `_M` matrix
  references (`"delivered"` → `"completed"`).
- `Kind.TERMINAL_SUCCESS` classification and `check_transition` logic:
  unchanged, just the code string.
- Rename backend identifiers that encode "delivery" as the completion
  action: `service_orders/service.py` functions/params referencing
  `delivered`, `completion_snapshot` (keep the column name — it's already
  correctly named for "completion", not "delivery"), any `errors.orders.*`
  message keys mentioning delivery-as-terminal-state.
- Update `frontend/src/i18n/bg.ts` keys and all frontend references to the
  `delivered` status code (`OrderHeader.tsx`, `KanbanBoard.tsx`,
  `OrderCard.tsx`, generated `transition-matrix.json` — re-run
  `backend/scripts/export_transition_matrix.py`).
- Update `test_committed_matrix_json_matches_statuses_py` fixtures and the
  migration regression test pattern (see `test_migration_0021_remove_testing_status.py`
  for the shape a `test_migration_00NN_...py` for this migration should take).
- E2E specs referencing `delivered`/"Предадена" text need updates
  (`order-delivery.spec.ts`, `order-invoice.spec.ts`) — coordinate with
  issue 02, since the dialog/button these specs drive is also being renamed.

## Acceptance criteria

- `uv run pytest` (full suite, DB-gated) green, including a new migration
  regression test for this migration.
- No remaining string literal `"delivered"` as a status code in
  `backend/src/serviceflow/` or `frontend/src/` (config/env vars named
  `delivery_method`/`delivery_address` are a different concept — item 12/13's
  shipping delivery — do not rename those).
- `lint-imports` and `tsc --noEmit` clean.
