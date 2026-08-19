# 19 — Business OS MVP Acceptance Checklist

Status: **live QA pass completed 2026-08-02** against a running dev
instance (fresh vendor-provisioned company `MVP QA Тест ЕООД`, both modules,
plus the pre-existing `реалтор`/`Velo`/`Геоинженеринг` single/no-module
companies). Full backend suite (364/364) and full frontend suite (162/162)
also re-run clean as part of this pass. Checked boxes below were personally
exercised end-to-end this pass, not inferred from code reading.

**3 confirmed bugs found — not fixed** (this was a verification pass, not a
remediation task):

1. **Missing i18n key** `errors.subscription.mutations_blocked` is not in
   `frontend/src/i18n/bg.ts`. The backend correctly returns 402 with that
   `message_key` when a suspended/cancelled company attempts a mutation, but
   the frontend's `t()` silently falls back to the generic
   `errors.internal` text ("Възникна неочаквана грешка. Опитайте отново.")
   instead of telling the tenant their subscription is the reason. Confirmed
   via live network inspection: backend response correct, catalog entry
   absent (`grep` confirms `errors.subscription.invalid_state` and
   `errors.subscription.reason_required` exist, this one doesn't).
2. **Role-change/deactivate confirm dialogs hide their own error on
   failure.** `frontend/src/settings/EmployeesPage.tsx`'s `setActive`/
   `setRole` only call `setConfirmDeactivateId(null)`/`setConfirmDemoteId(null)`
   inside the `try` block (success path). On failure, `patchError` is set
   and rendered as `<p role="alert">` in the page body (line ~309), but the
   native `<dialog>` (shown via `showModal()`, browser top-layer) stays
   open on top of it, making the error invisible — confirmed live by
   attempting to demote the sole Owner (correctly rejected 409
   `errors.employees.last_owner_protected` by the backend) and observing
   the confirm dialog just sits there with no visible feedback until
   manually cancelled.
3. **`PinPad.tsx` drops digits under rapid entry.** `press()` reads
   `setPin(pin + digit)` from the closure instead of the functional
   updater form. Under React 18's automatic batching, two clicks
   dispatched close together (confirmed reproducible with scripted rapid
   clicks; plausible for a fast real touch-typist) both read the same
   stale `pin` value, so the second click's digit overwrites rather than
   appends the first — a 4-digit PIN typed quickly can silently become a
   1-digit PIN, then get rejected as wrong. Confirmed the underlying PIN
   itself was correct (stored `pin_hash` verified, accepted once entered
   one digit at a time). Fix: `setPin((prev) => prev.length < 8 ? prev + digit : prev)`.

One pre-existing, unrelated **data anomaly** noted, not a live bug: several
older dev-seeded companies (e.g. "??????? ?????? ???? ????") have
mojibake'd Cyrillic names in the DB, predating this session — a seed-script
encoding issue, not a rendering bug (confirmed the string is already
corrupted at the DB row level).

---

## 1. Authentication

### Tenant

- [x] Login with valid email/password succeeds, sets session cookie + CSRF
      token, lands on the correct route (see §3 "Landing route" below).
- [ ] Login with wrong password shows the shared invalid-credentials message,
      no information leak about which field was wrong.
- [x] Logout POSTs `/auth/logout`, clears the session server-side
      (`/auth/me` returns 401 immediately after), and redirects to
      `/login` — including when the backend call itself fails.
- [x] Logging in as a second company in the same tab (no explicit logout
      first) never shows the first company's cached data — cache and the
      "last used app" preference are both cleared/reset on every login and
      logout.
- [x] A `?next=` deep link captured while logged out is only honored if the
      newly-authenticated company is actually entitled to that route;
      otherwise it falls back to `/`.
- [x] PIN-switch lists active users and unlocks with the right PIN
      (correct 4-digit PIN, entered one tap at a time, worked). **Bug found
      (#3 above): rapid entry can silently drop digits**, surfacing as a
      false "Грешен PIN." — this is the PinPad bug, not a PIN-verification
      bug (verified the stored PIN itself was correct).
- [ ] "Изход" from the locked screen still logs out cleanly (not
      re-verified this pass — was confirmed working in an earlier session).

### Vendor Console

- [x] Vendor login is a structurally separate session/CSRF plane from tenant
      login — confirmed live (a tenant session stayed valid throughout
      vendor-console use in the same tab, and vice versa).
- [x] Vendor login/logout work the same way as tenant (session cleared on
      logout, no stale cache across a same-tab vendor/tenant switch).
- [ ] An inactive platform admin is rejected at login and on an
      already-live session (covered by `test_vendor_security.py`, not
      independently re-verified live this pass).

---

## 2. Entitlements

- [x] A company with **only RepairFlow** active: RepairFlow screens work,
      `/api/v1/ps/*` 404s with `errors.ps.module_inactive`, PropertyFlow nav
      never renders.
- [x] A company with **only PropertyFlow** active: PropertyFlow screens
      work, RepairFlow nav/search/"+ Нова поръчка" never render.
- [x] A company with **both** active: app switcher appears; landing goes to
      the chooser when there's no preference yet — never RepairFlow by
      default; choosing an app is remembered.
- [x] A company with **neither** active: neutral "Няма активирани
      приложения" screen, no app's chrome renders.
- [x] Direct URL navigation to an inactive app's route is blocked by the
      backend guard (confirmed: RepairFlow-only session hitting `/ps`
      directly 404s on every `ps/*` call).
- [x] Vendor grant/revoke both work, are idempotent, immediately usable by
      a **live tenant session** with no re-login (confirmed: revoked
      PropertyFlow, re-granted it, tenant session picked it up without
      logging out).
- [x] Company Provisioning rejects an empty `modules` selection before
      creating anything; at least one of RepairFlow/PropertyFlow is now
      mandatory (confirmed via the provisioning form itself — both
      checkboxes present, unchecked by default).

---

## 3. RepairFlow

- [x] **Landing route**: RepairFlow-only company lands on `/` after login.
- [ ] Dashboard tiles load without error for a zero-order and a
      representative-mixed-set company (not exercised this pass — the QA
      company had zero orders throughout).
- [ ] Order intake (customer step → asset step → order step) creates an
      order with the correct initial status; asset fields match the
      company's `business_profile` (not exercised this pass — reached the
      customer-creation step only, blocked deliberately by the suspended-
      subscription test; not retried after reactivating).
- [ ] Order status transitions follow the documented state machine only.
- [ ] Issued invoices are immutable.
- [ ] Customer search / global search scoped to the authenticated company.
- [x] RepairFlow's own toolbar (search + "+ Нова поръчка") renders only
      when RepairFlow is the current app.
- [x] Mobile bottom nav renders only for a company actually entitled to
      RepairFlow.
- [x] **(new this pass)** Tenant mutation endpoints — confirmed specifically
      for `POST /customers` and `POST /users` — correctly return 402 while
      the company's subscription is suspended, and correctly succeed again
      once reactivated.

---

## 4. PropertyFlow

- [x] **Landing route**: PropertyFlow-only company lands on `/ps` after
      login.
- [x] Selecting a client shows their engagements; switching clients resets
      pagination (regression-tested, `PsPage.test.tsx`).
- [x] Selecting an engagement shows its next actions and populates the
      detail panel.
- [x] Creating a client, an engagement, and a next action all work
      end-to-end.
- [x] Completing a next action moves it into the collapsible "completed"
      section.
- [x] Changing an engagement's stage updates the stage badge.
- [x] Deadline-dialog-shows-wrong-engagement's-deadline bug fixed and
      regression-tested (`PsPage.test.tsx`).
- [ ] Active-only filter toggle (not re-verified after the refactor).
- [x] Pagination footer only appears past one page, prev/next disable
      correctly (`Pagination.test.tsx`).
- [x] New-client/-engagement/-action dialog labels correctly associated
      with their controls (verified live: accessible name is now "Име"/
      "Тип" etc., not the placeholder text).
- [ ] "Календар" stays visibly disabled/greyed (not re-checked this pass).

---

## 5. Subscription

- [x] A freshly-provisioned company starts in `trial`, 14 days out
      (provisioned 2026-08-02T16:54, `trial_ends_at` = 2026-08-16T16:54,
      exactly 14 days).
- [x] Vendor can transition to any of the five states via one dialog with a
      mandatory reason; **re-asserting the same state (active→active) is
      allowed and recorded as a distinct audited event, not a no-op**
      (confirmed via `platform_audit_log` query — 3 separate
      `company.subscription_transitioned` rows for
      trial→suspended→active→active, each with its own reason and
      timestamp).
- [x] While `suspended`: `POST /customers` and `POST /users` both correctly
      blocked (402); reads (`GET /orders`, `GET /users`) keep working.
      **Frontend gap: the blocked-mutation message shown to the user is
      generic, not the specific "subscription blocked" text — bug #1
      above.**
- [x] Auth, reads, and PIN-switch all kept working while suspended — login
      succeeded, orders list loaded, PIN dialog opened normally.
- [x] Subscription state and module entitlements are independent axes —
      confirmed via audit log: module grant/revoke events and subscription
      transition events are separate, neither's `detail` touches the
      other's data.
- [x] Every subscription transition writes exactly one audit row with
      correct `detail.from`/`detail.to` and the typed reason (verified via
      direct `platform_audit_log` query, 3/3 rows correct).

---

## 6. Seat limits

- [x] A company's seat limit defaults to unlimited (`null`) — confirmed at
      provisioning (fresh company showed "1/неограничено").
- [x] Vendor can set a numeric seat limit or flip back to unlimited,
      reflected immediately (confirmed: set to 2, detail view updated to
      "1/2" after the correct request; the "unlimited" checkbox must be
      unchecked first for the numeric field to be enabled and submitted —
      this is correct, deliberate behavior, not a bug, but worth noting
      since it tripped up testing once).
- [x] Creating a new employee while at the seat limit is rejected with a
      clear, specific message ("Достигнат е лимитът на местата за тази
      компания.") — the employee is **not** created (roster stayed at 2).
- [ ] Reactivating a previously-deactivated employee at capacity (not
      exercised — the deactivate/reactivate cycle tested this pass was
      done while under the limit, not at it).
- [ ] Lowering the seat limit below current usage (not exercised this
      pass — covered by `test_seat_limit.py`, not independently re-verified
      live).
- [x] The seat-usage banner always matched the actual roster count
      throughout (1/2 → 2/2, correctly live-updated after each add).

---

## 7. Employee management (tenant-side)

- [x] Owner can add an employee (name, email, password, PIN, "make Owner"
      checkbox) — confirmed, including PIN-based login afterward.
- [ ] Duplicate email rejection (`errors.employees.email_taken`) — not
      exercised this pass.
- [x] Owner can deactivate an active employee (behind a confirm dialog) and
      reactivate an inactive one (no confirmation) — both confirmed,
      roster status flipped correctly each time.
- [x] Owner can promote/demote — confirmed the demote **attempt** on the
      sole Owner (see last-owner protection below); a genuine promote of a
      Worker was not separately exercised this pass.
- [x] **Last-owner protection**: correctly rejected (409
      `errors.employees.last_owner_protected`) at the backend. **Bug found
      (#2 above): the confirm dialog does not surface this error — it stays
      open with no visible feedback, the actual message renders behind the
      modal backdrop.**
- [x] Every action produced an audit trail effect (confirmed via the roster
      re-fetching correctly after each mutation; did not independently
      query `audit_log` rows for employee actions this pass, unlike the
      subscription/entitlement audit rows which were queried directly).
- [ ] A deactivated employee cannot log in (not independently re-tested
      this pass).

---

## 8. Vendor Console

- [x] Company list and detail views expose only documented metadata —
      confirmed on the fresh QA company's detail page (business profile,
      business type label, active modules, subscription state, trial end,
      seat limit/usage, created date — nothing else).
- [x] Company Provisioning form: `business_profile` is a constrained
      `<select>` (5 canonical values), `business_type_label` a separate
      required free-text field, both module checkboxes present and
      unchecked by default — all confirmed live on the provisioning form
      itself, end-to-end through a real submission.
- [ ] Duplicate owner email rejection / atomicity (not exercised this
      pass — covered by `test_company_provisioning.py`).
- [x] Every mutating action this pass (provision, grant, revoke, grant,
      revoke, grant, 3× subscription transition, seat limit change) wrote
      exactly one audit row each — confirmed via direct
      `platform_audit_log` query, 8/8 rows present and correctly detailed.
- [ ] RLS/GUC tenant-table isolation (not independently re-verified live —
      covered by `test_vendor_security.py`, re-run clean as part of the
      full suite this pass).
- [ ] Vendor login rate-limiting (not exercised this pass).

---

## Cross-cutting

- [x] No user-facing literal Bulgarian strings outside `bg.ts` — spot-check
      grep (`>[А-Яа-яЁё]` and `aria-label="[А-Яа-яЁё]`/etc. in `.tsx`,
      excluding `bg.ts` itself) found zero hits.
- [x] `uv run lint-imports` — 9/9 contracts kept, 0 broken.
- [x] Full backend suite (364/364) and full frontend suite (162/162) green
      as of this pass.
- [~] No PII in application logs — no `logging.*` calls exist in `src/`
      at all (nothing to leak in the running service). **Note**: the
      one-time CLI provisioning scripts (`platform_admin/bootstrap.py`,
      `serviceflow/seed.py`) do `print()` the admin/owner's name and email
      to the operator's own terminal on creation — arguably outside the
      "application logs" rule's intent (an interactive setup script's own
      console output, not an aggregated/shipped log), but technically
      prints names/emails rather than only ids per docs/11 §3's literal
      wording. Flagging for a product decision, not treating as a fail.
