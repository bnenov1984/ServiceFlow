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

## Domain ownership and growth rules

Both files above are flat at the E2E root today, but each already has a
conceptual home:

- `auth.spec.ts` → future `platform/` domain
- `customer.spec.ts` → future `repairflow/` domain

Neither moves yet — see materialization rule below.

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
