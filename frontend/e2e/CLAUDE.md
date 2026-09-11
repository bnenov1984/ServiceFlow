# frontend/e2e/ — Local Router

Applies only to work inside this subtree. Root [../../CLAUDE.md](../../CLAUDE.md)
remains authoritative for all repository-wide hard rules — nothing here restates
or overrides them. For broader application knowledge see
[../../docs/INDEX.md](../../docs/INDEX.md).

This directory contains the BusinessOS Playwright end-to-end tests: browser-driven
tests that exercise the running frontend (and the backend behind it) as a real
user would, as opposed to the unit tests under `frontend/src/`.

## Before modifying tests

1. Read the relevant module-level `CLAUDE.md` if one exists for the area under test.
2. Inspect existing specs for the same workflow — don't duplicate coverage.
3. Reuse fixtures/helpers instead of re-deriving login or setup steps inline.
4. Prefer stable Playwright locators (`getByRole`, `getByLabel`) over CSS
   selectors or text matches that are likely to shift with copy changes.
5. Avoid test execution-order dependencies — each test must set up its own
   state and not rely on a prior test having run first.
6. Run the smallest relevant test scope first (e.g. a single file or `-g` grep
   for one test) before running the full suite.

## Configuration

- `E2E_BASE_URL` — the target environment the tests run against (set in
  `playwright.config.ts` as `use.baseURL`). CI points this at the deployed
  Render frontend; locally, point it at your dev server or a staging URL.
- Credentials/secrets must come from environment variables and must never be
  hardcoded in a spec. CI supplies these from GitHub Actions secrets.

## Existing tests

### `auth.spec.ts`

Covers login at `/`:

- **owner can login** — fills the Bulgarian-labeled email/password fields
  (`Имейл` / `Парола`) with `E2E_OWNER_EMAIL` / `E2E_OWNER_PASSWORD`, submits
  (`Влез`), and asserts navigation to `/choose-app` with the `RepairFlow` app
  button visible.
- **owner cannot login with invalid password** — same flow with a wrong
  password, asserts redirect to `/login?next=%2F` and a Bulgarian error alert
  (`Грешен имейл или парола.`).

Both tests throw early if the required env vars aren't set, rather than
failing on a blank-field assertion.

### `customer.spec.ts`

Logs in as owner (same pattern as above), enters the RepairFlow app, and
creates a customer via the "+ Нова поръчка" → "+ Нов клиент" flow, asserting
the new customer name appears in the UI.

### `order-intake.spec.ts`

Logs in as owner, enters RepairFlow, and drives the full three-step intake
flow to a real created order: "+ Нова поръчка" → new customer (same as
`customer.spec.ts`) → new asset ("Друго", submitted with no fields — every
asset field is optional at the API) → order step (complaint only — the
textarea has no accessible label/placeholder, a real pre-existing gap in
`OrderStep.tsx`, so it's targeted structurally as the page's only
`<textarea>`) → submit. Asserts navigation to `/orders/:id` and that the
order-number heading and the complaint text are both visible on the order
detail page.

### `order-status.spec.ts`

Repeats `order-intake.spec.ts`'s setup to get a real order onto the board
(login → RepairFlow → intake), confirms it starts at "Приета" (received,
docs/01 BR-1), then drives the "Промени статус" menu (`OrderHeader.tsx`'s
`StatusTransitionMenu`, `role="menu"`/`role="menuitem"`) to advance it to
"Диагностика" — the matrix's plain "ok" next step from "received", the one
transition with no reason/approval/delivery dialog attached
(`OrderHeader.tsx`'s `requestTransition`). Asserts the new status is visible
and the old one no longer is. Deliberately doesn't touch the Kanban board's
drag-and-drop path (same underlying transition, a separate and more brittle
interaction surface) or any transition that opens a dialog (skip-ahead
"warn" transitions, the terminal-failure reason dialog, delivery) — those are
each their own future test, not bundled into this one.

### `order-delivery.spec.ts`

Same intake setup, then drives the *entire* clean lifecycle in one pass:
received → diagnostics → repair → ready (three no-dialog "ok" transitions,
same menu as `order-status.spec.ts`) → delivered, which opens
`DeliveryDialog` (fills warranty days, leaves payment blank since it's
optional, confirms). Deliberately never clicks "Печат на протокол" — that
path hits a known, separately-tracked fpdf crash
(`backend/tests/test_protocol.py`, `xfail(strict=True)`) unrelated to the
status transition this test verifies. Two things worth knowing if this file
needs touching again:

- **Real bug found and fixed here, not a test workaround**:
  `OrderHeader.tsx`'s `runStatusChange`/`runDelivery`/etc. all await
  `POST → refreshOrder() → close()`. Clicking through consecutive
  transitions fast enough that a *previous* transition's async chain is
  still in flight let its stale `close()` call clear the pending state a
  *newer* action had just set — a delivery dialog opened by transition N+1
  could close itself ~1s later from transition N's trailing cleanup. Fixed
  with an operation-token guard (`actionTokenRef`/`openPending` in
  `OrderHeader.tsx`) so a superseded action's completion can't touch shared
  `pending`/`submitting`/`error` state anymore. This test is what surfaced
  it — root-caused by instrumenting `setPending`/`HTMLDialogElement.close`
  with a throwaway diagnostic spec (not committed), not guessed at.
- The test itself still waits for the network to go idle
  (`page.waitForLoadState('networkidle')`) after each transition before
  starting the next, as defense in depth and more realistic pacing — not a
  substitute for the app fix above, which is what actually makes this safe
  to click through quickly at all.
- `Dialog.tsx`'s `<h2>` title isn't `aria-labelledby`'d to the `<dialog>`
  element (a real, separate accessibility gap, same shape as `OrderStep`'s
  complaint textarea) — the dialog carries no accessible name, so it's
  matched by bare role plus a separate visible-text check on the title,
  not `getByRole('dialog', { name: ... })`.

## Domain ownership and growth rules

All five files above are flat at the E2E root today, but each already has a
conceptual home:

- `auth.spec.ts` → future `platform/` domain
- `customer.spec.ts`, `order-intake.spec.ts`, `order-status.spec.ts`,
  `order-delivery.spec.ts` → future `repairflow/` domain

`repairflow/` now has four specs — the materialization rule below says
that's enough to justify the directory, but none moves yet; do it as its own
change, not a side effect of adding another file.

**Future top-level QA domains** (none exist as directories yet):

- `platform/` — BusinessOS Core: login/session, app chooser, `settings/employees`,
  `settings/company`.
- `repairflow/` — RepairFlow app: orders, intake, customers, invoices, dashboard.
- `professional-services/` — PropertyFlow app.
- `vendor/` — Vendor Control Plane (`/vendor/*`). **Must remain a sibling of the
  other domains, never nested under `platform/`** — the app keeps vendor and
  tenant sessions structurally isolated (vendor is never reachable from a
  tenant session), and nesting vendor tests under `platform/` would invite the
  fixture-sharing the app deliberately prevents.

**When a domain becomes a real directory:** only once it has two or more
meaningful specs (one file doesn't yet create a navigation problem a directory
would solve), or it carries non-obvious operational knowledge that needs
routing regardless of file count (e.g. an isolation rule or a fixture hazard).
Don't create a directory for a domain with no tests yet.

**When a domain directory gets its own `CLAUDE.md`:** only when there's
genuine domain-specific knowledge to route — not automatically on directory
creation. When one is created, it should point upward to this file and to
`../../CLAUDE.md` / `../../docs/INDEX.md` rather than restate conventions
(env vars, credentials, locators) already covered here.

**Notes:**

- `customer.spec.ts` is currently misnamed for what it tests — it's a
  RepairFlow intake/order-flow test (customer creation happens inside the
  "+ Нова поръчка" dialog), not a standalone customer-resource test. Worth
  renaming once `repairflow/` is materialized; not renamed now.
- `docs/12_TESTING_STRATEGY.md` §3's "five E2E journeys" predate the
  BusinessOS multi-app pivot (PIN switches, протокол print, single-tenant
  flows) and don't map cleanly onto today's routes. Treat that list as
  historical context, not a checklist, until it's revalidated against the
  current architecture.
