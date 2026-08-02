# 19 — Business OS MVP Acceptance Checklist

Status: draft, first pass. Covers Vendor Console, RepairFlow, PropertyFlow,
Authentication, Entitlements, Subscription, Seat limits, Employee management.
Each item is phrased as an observable, pass/fail check against the current
implementation — not aspirational. Items marked **(verified this session)**
were exercised live against the running app during recent work; everything
else needs a fresh manual pass before sign-off.

How to use: work top to bottom against a clean dev DB (or a disposable
vendor-provisioned company set), checking off each box. A failed item blocks
MVP sign-off unless explicitly waived with a written reason.

---

## 1. Authentication

### Tenant

- [ ] **(verified)** Login with valid email/password succeeds, sets session
      cookie + CSRF token, lands on the correct route (see §3 "Landing route"
      below).
- [ ] Login with wrong password shows the shared invalid-credentials message,
      no information leak about which field was wrong.
- [ ] **(verified)** Logout POSTs `/auth/logout`, clears the session
      server-side (`/auth/me` returns 401 immediately after), and redirects
      to `/login` — including when the backend call itself fails (network
      error), the button must still land the user on `/login`.
- [ ] Logging in as a second company in the same tab (no explicit logout
      first) never shows the first company's cached data (dashboard,
      customers, orders, PropertyFlow clients/engagements) — **(verified)**
      cache and the "last used app" preference are both cleared/reset on
      every login and logout.
- [ ] A `?next=` deep link captured while logged out is only honored if the
      newly-authenticated company is actually entitled to that route;
      otherwise it falls back to `/` — **(verified)**.
- [ ] PIN-switch ("Смяна на потребител" / lock screen) correctly locks the
      screen, lists active users, and unlocks with the right PIN; wrong PIN
      is rejected; "Изход" from the locked screen still logs out cleanly.
      *(Discovered live during this session's QA — not yet exercised as a
      deliberate pass; confirm PIN entry itself, not just the escape hatch.)*

### Vendor Console

- [ ] Vendor login is a structurally separate session/CSRF plane from tenant
      login — a tenant session cookie never grants Vendor Console access and
      vice versa **(verified — `test_vendor_security.py`)**.
- [ ] Vendor login/logout work the same way as tenant (session cleared on
      logout, no stale cache across a same-tab vendor-then-tenant or
      tenant-then-vendor switch) **(verified)**.
- [ ] An inactive platform admin is rejected at login and on an already-live
      session.

---

## 2. Entitlements

- [ ] A company with **only RepairFlow** active: RepairFlow screens work,
      `/api/v1/ps/*` 404s with `errors.ps.module_inactive`, PropertyFlow nav
      never renders **(verified)**.
- [ ] A company with **only PropertyFlow** active: PropertyFlow screens
      work, `/api/v1/customers` (and the other 8 RepairFlow-owned routers)
      404 with `errors.repairflow.module_inactive`, RepairFlow nav/search/
      "+ Нова поръчка" never render **(verified)**.
- [ ] A company with **both** active: app switcher appears; landing goes to
      the remembered last-used app, or the chooser screen if there's no
      preference yet — never RepairFlow by default **(verified)**.
- [ ] A company with **neither** active: neutral "Няма активирани
      приложения" screen, no app's chrome renders, both APIs 404
      **(verified)**.
- [ ] Direct URL navigation to an inactive app's route is blocked by the
      backend guard regardless of what the frontend nav shows or hides
      **(verified)**.
- [ ] Vendor grant (`PUT /platform-admin/companies/{id}/modules/{key}`) and
      revoke (`DELETE` same path) both work, are idempotent (granting an
      already-active module / revoking an already-inactive one still
      returns 200 with `changed: false`), and each call is audited even
      when a no-op.
- [ ] A newly-granted module is usable by a **live tenant session**
      immediately, with no re-login required.
- [ ] Company Provisioning rejects an empty `modules` selection with
      `errors.provisioning.no_modules_selected` before creating anything —
      **(verified)**; at least one of RepairFlow/PropertyFlow is mandatory
      at provisioning time going forward.

---

## 3. RepairFlow

- [ ] **Landing route**: RepairFlow-only company lands on `/` (its own
      dashboard) after login, never redirected elsewhere **(verified)**.
- [ ] Dashboard tiles (active orders, waiting parts, ready, overdue, today's
      tasks, call tasks) load without error for a company with zero orders
      and for one with a representative mixed set.
- [ ] Order intake (customer step → asset step → order step) creates an
      order with the correct initial status; the asset's fields match the
      `business_profile` seeded for that company (e.g. a `phone_repair`
      company gets phone-shaped asset types, not generic ones).
- [ ] Order status transitions follow the documented state machine only
      (docs/01 BR rules) — an illegal transition is rejected, not silently
      accepted.
- [ ] Issued invoices are immutable — no code path can edit line items or
      totals on an order past invoicing.
- [ ] Customer search / global search returns results scoped to the
      authenticated company only (no cross-tenant leakage).
- [ ] RepairFlow's own toolbar (search + "+ Нова поръчка") renders only
      when RepairFlow is the current app, never for PropertyFlow
      **(verified)**.
- [ ] Mobile bottom nav (Табло/Поръчки/Клиенти) renders only for a company
      actually entitled to RepairFlow **(verified — this was a real bug:
      it used to render unconditionally for every company)**.

---

## 4. PropertyFlow

- [ ] **Landing route**: PropertyFlow-only company lands on `/ps` after
      login, RepairFlow nav never renders **(verified)**.
- [ ] Selecting a client shows their engagements; selecting a different
      client clears the previously-selected engagement and resets the
      engagement list's pagination to page 1 **(verified — regression test
      added, `PsPage.test.tsx`)**.
- [ ] Selecting an engagement shows its next actions and populates the
      bottom detail panel (client, status, official deadline, internal
      target) **(verified)**.
- [ ] Creating a client, an engagement (optionally from a workflow
      template), and a next action all work end-to-end and appear in their
      respective columns without a manual refresh **(verified)**.
- [ ] Completing a next action moves it into the collapsible "completed"
      section and is excluded from the open list **(verified)**.
- [ ] Changing an engagement's stage updates the stage badge and the
      right-hand stages panel's current-stage marker **(verified)**.
- [ ] Changing an engagement's deadline requires a reason, is recorded in
      the "История" tab, and **reopening the deadline dialog for a
      different engagement shows that engagement's own current deadline,
      not the previously-viewed one's** **(verified — this was a real bug,
      fixed and regression-tested this session)**.
- [ ] Client and engagement search/filter (name search, stage filter,
      active-only toggle) narrow the list correctly and reset pagination
      **(verified for search; active-only toggle not yet re-verified after
      the refactor)**.
- [ ] Pagination footer only appears once a column exceeds one page
      (8 items) and prev/next correctly disable at the ends
      **(verified — `Pagination.test.tsx`)**.
- [ ] New-client / new-engagement / new-action dialog form fields are
      properly labeled for assistive tech (associated `<label for>`, not
      just placeholder text) **(verified — this was a real bug across 3
      dialogs, fixed this session)**.
- [ ] "Календар" stays visibly disabled/greyed — no dead click target.

---

## 5. Subscription

- [ ] A freshly-provisioned company starts in `trial`, 14 days out, and
      `trial_ends_at` is shown correctly in the Vendor Console detail view.
- [ ] Vendor can transition a company's subscription state to any of the
      five states (`trial`, `active`, `grace_period`, `suspended`,
      `cancelled`) via one dialog; a mandatory, non-blank `reason` is
      required; re-asserting the *same* state is allowed and still
      recorded as a distinct audited event (not treated as a no-op).
- [ ] While `suspended` or `cancelled`: tenant **mutation** endpoints
      (creating/editing orders, customers, PropertyFlow clients/
      engagements, etc.) are blocked with `errors.subscription.
      mutations_blocked`; **reads** keep working unaffected — a suspended
      tenant can still view their data.
- [ ] Auth/logout/PIN-switch keep working even while `suspended` — the
      tenant is never locked out of the app shell itself, only blocked from
      writing.
- [ ] Subscription state and module entitlements are independent axes —
      suspending a company does not touch `active_modules`, and revoking a
      module does not touch subscription state.
- [ ] Every subscription transition writes exactly one
      `platform_audit_log` row with the correct `detail.from`/`detail.to`
      and the vendor's typed reason.

---

## 6. Seat limits

- [ ] A company's seat limit defaults to unlimited (`null`) unless the
      vendor sets one explicitly.
- [ ] Vendor can set a numeric seat limit or flip back to "неограничено"
      via the company detail view; the change is reflected immediately and
      audited (`company.seat_limit_changed`, with `detail.from`/`detail.to`).
- [ ] Creating a new employee while at the seat limit is rejected with
      `errors.employees.seat_limit_reached`; the employee is **not**
      created (no partial state).
- [ ] Reactivating a previously-deactivated employee counts against the
      same limit and is rejected the same way if at capacity.
- [ ] Lowering the seat limit below the company's *current* active-employee
      count is allowed (no retroactive deactivation) — enforcement only
      kicks in on the next create/reactivate attempt.
- [ ] The Employees page's seat-usage banner (`used/limit`) always matches
      the actual count of active employees.

---

## 7. Employee management (tenant-side)

- [ ] Only the company Owner sees "Настройки" as a real link; a Worker sees
      it permanently greyed, and direct navigation to `/settings/employees`
      as a Worker shows an access-denied state, not the employee list.
- [ ] Owner can add an employee (name, email, password, optional PIN,
      optional "make Owner" checkbox); email must be globally unique across
      the whole platform, not just this company — a duplicate is rejected
      with `errors.employees.email_taken`.
- [ ] Owner can deactivate an active employee (behind a confirm dialog) and
      reactivate an inactive one (no confirmation needed, mirroring
      entitlement grant's unconfirmed-additive posture).
- [ ] Owner can promote a Worker to Owner and demote an Owner to Worker.
- [ ] **Last-owner protection**: the last active Owner cannot be
      deactivated or demoted — both actions are rejected with
      `errors.employees.last_owner_protected`, and the UI surfaces that
      message rather than failing silently.
- [ ] Every create/deactivate/reactivate/role-change is written to the
      tenant `audit_log` (`employee_created`/`employee_updated`) — distinct
      from the Vendor Console's `platform_audit_log`.
- [ ] A deactivated employee cannot log in, but their historical records
      (orders they worked, audit trail) remain intact and attributed to
      them.

---

## 8. Vendor Console

- [ ] Company list and detail views expose **only** documented
      administrative metadata (name, business profile, business type
      label, active modules, subscription state, trial end date, seat
      limit/usage, created date) — never tenant operational data
      (customers, orders, invoices) and never PII beyond what's
      sanctioned.
- [ ] Company Provisioning form: `business_profile` is a constrained
      `<select>` (five canonical values, controls RepairFlow asset-type
      seeding); `business_type_label` is a separate, required free-text
      field purely for the vendor's own description, and **never**
      influences validators, asset schemas, or workflows; at least one
      module checkbox (RepairFlow/PropertyFlow) is required.
- [ ] A duplicate owner email at provisioning time is rejected
      (`errors.provisioning.owner_email_taken`) and leaves **zero** trace —
      no orphaned company, owner, or audit row (atomicity).
- [ ] Every CSRF-guarded (mutating) Vendor Console route writes exactly one
      audit row; every read-only route writes none — this is covered
      generically by a structural test
      (`test_every_vendor_mutation_route_writes_an_audit_record` /
      `test_no_vendor_read_route_writes_an_audit_record`) and should stay
      green as new vendor mutations are added.
- [ ] Vendor Console never reads or writes any tenant-scoped table directly
      (RLS/GUC boundary) — covered by
      `test_vendor_request_reads_no_tenant_table` /
      `test_vendor_request_never_sets_the_tenant_rls_guc`; re-run as a
      regression check, don't just trust the test file's age.
- [ ] Vendor login is rate-limited against brute-force attempts.

---

## Cross-cutting (not owned by one section, but blocks sign-off if broken)

- [ ] No user-facing literal Bulgarian strings live outside
      `frontend/src/i18n/bg.ts` — spot-check any screen touched during MVP
      hardening.
- [ ] `backend/.importlinter` contracts stay green (`uv run lint-imports`) —
      domain modules never import `platform`, Vendor Control Plane never
      imports tenant code.
- [ ] Full backend suite (`uv run pytest` against `serviceflow_test`) and
      full frontend suite (`npm run test`) are green, `npm run build`
      produces no TypeScript errors, before every MVP-candidate commit.
- [ ] No PII appears in application logs.
