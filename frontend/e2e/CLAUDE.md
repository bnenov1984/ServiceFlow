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

## Shared helpers (`support/login.ts`)

- `getOwnerCredentials()` — reads `E2E_OWNER_EMAIL`/`E2E_OWNER_PASSWORD` and
  throws early if either is unset, rather than failing later on a blank field.
- `loginAsOwner(page, email, password)` — fills the Bulgarian-labeled login
  form at `/` and submits it.
- `enterRepairFlow(page)` — **every spec's entry point after login.** Clicks the
  app chooser's RepairFlow button only if the chooser is actually showing, then
  waits for `/orders`. This is deliberately tolerant of two tenant shapes:
  IndexRoute (`frontend/src/App.tsx`) sends a RepairFlow-only company straight
  to `/orders` and reaches `/choose-app` only when both applications are active.
  Since the 11.09.2026 one-application-per-company decision
  (`platform_admin.service.grant_entitlement`) a co-entitled company can no
  longer be provisioned, and `serviceflow.seed` seeds RepairFlow only to match
  (20.09.2026) — but the long-lived deployed tenant the `e2e` job targets may
  still be co-entitled from before that change. One helper covers both instead
  of forking the specs on their target environment. Don't re-add a
  `toHaveURL('/choose-app')` assertion to a spec: it pins the suite to a tenant
  shape production forbids. The chooser's own five routing branches are
  unit-tested in `frontend/src/App.routing.test.tsx`, which is where that
  behavior belongs.

## Existing tests

### `auth.spec.ts`

Stays flat at the E2E root — `platform/` isn't materialized yet (only one
spec lives there conceptually so far; see the materialization rule below).

Covers login at `/`:

- **owner can login** — fills the Bulgarian-labeled email/password fields
  (`Имейл` / `Парола`) with `E2E_OWNER_EMAIL` / `E2E_OWNER_PASSWORD`, submits
  (`Влез`), then reaches the app through `enterRepairFlow()` and asserts
  RepairFlow's own toolbar action ("+ Нова поръчка") is visible. It asserts no
  specific landing URL — that would pin the test to one tenant's module shape
  (see **Shared helpers** above).
- **owner cannot login with invalid password** — same flow with a wrong
  password, asserts redirect to `/login?next=%2F` and a Bulgarian error alert
  (`Грешен имейл или парола.`).

Both tests throw early if the required env vars aren't set, rather than
failing on a blank-field assertion.

### `repairflow/order-intake-customer.spec.ts`

Logs in as owner (same pattern as above), enters the RepairFlow app, and
creates a customer via the "+ Нова поръчка" → "+ Нов клиент" flow, asserting
the new customer name appears in the UI. (Renamed from `customer.spec.ts` —
it's an intake-flow test, not a standalone customer-resource test; see the
notes below.)

### `repairflow/order-intake.spec.ts`

Logs in as owner, enters RepairFlow, and drives the full three-step intake
flow to a real created order: "+ Нова поръчка" → new customer (same as
`order-intake-customer.spec.ts`) → new asset ("Друго", submitted with no fields — every
asset field is optional at the API) → order step (complaint only — the
textarea has no accessible label/placeholder, a real pre-existing gap in
`OrderStep.tsx`, so it's targeted structurally as the page's only
`<textarea>`) → submit. Asserts navigation to `/orders/:id` and that the
order-number heading and the complaint text are both visible on the order
detail page.

### `repairflow/order-status.spec.ts`

Repeats `order-intake.spec.ts`'s setup to get a real order onto the board
(login → RepairFlow → intake), confirms it starts at "Приета" (received,
docs/01 BR-1), then drives the "Промени статус" menu (`OrderHeader.tsx`'s
`StatusTransitionMenu`, `role="menu"`/`role="menuitem"`) to advance it to
"Диагностика" — the matrix's plain "ok" next step from "received", the one
transition with no reason/approval/completion dialog attached
(`OrderHeader.tsx`'s `requestTransition`). Asserts the new status is visible
and the old one no longer is. Deliberately doesn't touch the Kanban board's
drag-and-drop path (same underlying transition, a separate and more brittle
interaction surface) or any transition that opens a dialog (skip-ahead
"warn" transitions, the terminal-failure reason dialog, completion — the
last of which, since 2026-09-25, is its own dedicated button on
`OrderHeader.tsx`, not a dropdown transition at all) — those are each their
own future test, not bundled into this one.

### `repairflow/order-delivery.spec.ts`

Same intake setup, then drives the *entire* clean lifecycle in one pass:
received → diagnostics → repair → ready (three no-dialog "ok" transitions,
same menu as `order-status.spec.ts`) → completed. **Since the 2026-09-25
audit correction, "completed" ("Приключена", renamed from "delivered"/
"Предадена") is no longer offered through the "Промени статус" dropdown at
all** — it has its own dedicated primary button, "Приключи поръчката",
shown only on a `ready` order (`OrderHeader.tsx`). Clicking it opens
`CompletionDialog` (renamed from `DeliveryDialog`; fills warranty days,
leaves payment blank since it's optional, confirms via the "Приключи"
button — scope that locator with `{ exact: true }`, since the header's own
"Приключи поръчката" button is still in the DOM behind the open dialog and
would otherwise substring-match too). Deliberately never clicks "Печат на
протокол" — that path hits a known, separately-tracked fpdf crash
(`backend/tests/test_protocol.py`, `xfail(strict=True)`) unrelated to the
status transition this test verifies. Things worth knowing if this file
needs touching again:

- **Real bug found and fixed here, not a test workaround**:
  `OrderHeader.tsx`'s `runStatusChange`/`runComplete`/etc. all await
  `POST → refreshOrder() → close()`. Clicking through consecutive
  transitions fast enough that a *previous* transition's async chain is
  still in flight let its stale `close()` call clear the pending state a
  *newer* action had just set — a completion dialog opened by transition
  N+1 could close itself ~1s later from transition N's trailing cleanup.
  Fixed with an operation-token guard (`actionTokenRef`/`openPending` in
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

### `repairflow/order-invoice.spec.ts`

Same delivery flow as `order-delivery.spec.ts`, then issues an invoice
against the delivered order. Two setup steps that aren't obvious from the
happy-path UI:

- **Seller setup is required first.** `commercial/service.py`'s `issue()`
  rejects with `errors.invoices.seller_incomplete` unless the company has
  an address and a checksum-valid EIK (`company/requisites`,
  `CompanyRequisitesPage.tsx` at `/settings/company`) — a freshly seeded
  company has neither. The test fills both before touching an order, using
  `"130489869"`, the same known-valid test EIK the backend invoice suite
  already uses (`test_invoice_issue.py` and siblings). The buyer side needs
  no equivalent setup: the test customer stays an individual (the intake
  form's default), and `_buyer_snapshot` only demands address/EIK for
  company buyers.
- **The order has no part/labor lines** (asset type "Друго", nothing added
  at intake), so the draft invoice starts empty — `InvoiceDraftEditor`'s
  Issue button is disabled while empty, and the backend independently
  rejects an empty draft (`errors.invoices.empty`) regardless of the UI
  guard. The test adds one manual line before saving.

Other things worth knowing:

- **Issue posts the server-persisted draft, not local edits** —
  `submitIssue` never saves first, so Save is a hard prerequisite to Issue,
  not just good practice before navigating away.
- **The order page has several sections with an identically-labeled
  "Добави" button** (Задачи, Аксесоари, and the invoice line editor itself)
  — every invoice-card interaction in this test is scoped to a locator
  rooted at the "Фактура" heading's parent, not matched page-wide.
- **The outer "Издай фактура" button and the issue-confirmation dialog's
  own confirm button share the same label** (`order.invoice_button`, used
  for both) — the first click is scoped to the invoice card (unambiguous
  before the dialog exists), the second to `page.getByRole('dialog')`.
- A freshly created draft does not reliably land expanded — the test opens
  it explicitly ("Отвори") rather than assuming `InvoiceEntry`'s
  `defaultOpen` took effect.

### `repairflow/order-rejection.spec.ts`

Journey 2's first half (docs/12 §3 «оценка → отказ»): intake (same setup as
`order-intake.spec.ts`) → received → **диагностика** → **отказана**.
`"declined"` is a `TERMINAL_FAILURE_CODES` entry (`OrderHeader.tsx`), rendered
in the status menu's separate red failure section below a divider — still a
plain `role="menuitem"`. It opens `ReasonDialog`, and the spec asserts the
confirm button is *disabled until a reason is typed*, mirroring the backend's
own `reason_required` rule before any round-trip happens. Ends on the terminal
state's own invariants: the status-change menu disappears
(`!archived && !orderIsTerminal`) while the intake protocol button stays
visible — asserted visible only, never clicked, for the same fpdf reason as
`order-delivery.spec.ts`.

**Not yet covered:** the journey's second half — такса диагностика invoice →
плащане against the declined order. That's the natural next spec here.

### `repairflow/order-status-cache.spec.ts`

Regression for PO bugs #23/#30 (24.10.2026): a status changed from the orders
list (`OrderStatusActions`) showed the *old* status on the order page, and a
just-created order was missing from the list, for up to the global 30 s
`staleTime` (`src/main.tsx`) — each view invalidated only its own query keys.
Fixed by one shared `invalidateOrderViews` (`src/lib/orderQueries.ts`) used by
the order header, the orders page (list + Kanban) and intake. Three tests:
intake → list, list → order page (#23), Чака клиент → Чака части with approval
from the list → order page (#30). Two things that matter if this file is
touched:

- **Navigate client-side** (the „← Поръчки" link, row links), never
  `page.goto` between the change and the assertion — a full load starts with
  an empty cache and hides the bug.
- The #23/#30 tests `page.reload()` once before opening the list on purpose,
  so they exercise only the order-page cache, not the intake → list case the
  first test covers.

## Domain ownership and growth rules

**`repairflow/` is now a real directory** (materialized 2026-09-12): it holds
`order-intake-customer.spec.ts`, `order-intake.spec.ts`, `order-status.spec.ts`,
`order-delivery.spec.ts`, `order-invoice.spec.ts`, `order-rejection.spec.ts`,
`order-status-cache.spec.ts` — seven specs, all importing the shared `../support/login` helpers (note the `../`,
not `./`, from inside the subdirectory). `auth.spec.ts` stays flat at the E2E root for now — it's
the only spec conceptually belonging to `platform/`, and the materialization
rule below says one file isn't yet enough to justify a directory.

**Future top-level QA domains** (only `repairflow/` exists as a directory so far):

- `platform/` — BusinessOS Core: login/session, app chooser, `settings/employees`,
  `settings/company`. Not materialized yet — only `auth.spec.ts` exists
  conceptually here.
- `repairflow/` — RepairFlow app: orders, intake, customers, invoices, dashboard.
  **Materialized.**
- `professional-services/` — PropertyFlow app. No specs exist yet.
- `vendor/` — Vendor Control Plane (`/vendor/*`). No specs exist yet. **Must
  remain a sibling of the other domains, never nested under `platform/`** —
  the app keeps vendor and tenant sessions structurally isolated (vendor is
  never reachable from a tenant session), and nesting vendor tests under
  `platform/` would invite the fixture-sharing the app deliberately prevents.

**When a domain becomes a real directory:** only once it has two or more
meaningful specs (one file doesn't yet create a navigation problem a directory
would solve), or it carries non-obvious operational knowledge that needs
routing regardless of file count (e.g. an isolation rule or a fixture hazard).
Don't create a directory for a domain with no tests yet — this is exactly why
`platform/`, `professional-services/`, and `vendor/` stay unmaterialized above
despite being named.

**When a domain directory gets its own `CLAUDE.md`:** only when there's
genuine domain-specific knowledge to route — not automatically on directory
creation. `repairflow/` doesn't have one yet; nothing routed there is specific
enough to that subdirectory alone (the notes below apply repo-wide E2E
knowledge, not repairflow-only knowledge). When one is created, it should
point upward to this file and to `../../CLAUDE.md` / `../../docs/INDEX.md`
rather than restate conventions (env vars, credentials, locators) already
covered here.

**Notes:**

- `docs/12_TESTING_STRATEGY.md` §3's "five E2E journeys" predate the
  BusinessOS multi-app pivot (PIN switches, протокол print, single-tenant
  flows) and don't map cleanly onto today's routes. Treat that list as
  historical context, not a checklist, until it's revalidated against the
  current architecture.
