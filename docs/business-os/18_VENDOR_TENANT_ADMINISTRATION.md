# BOS-18 — Vendor & Tenant Administration: Audit and Target Model

Status: **Documentation-first audit + target model — Accepted with two PO
clarifications applied 26.07.2026** (C1: business-profile ownership is
vendor-assigned at provisioning, not a tenant preference — §5 Q5, ADR-BOS-011;
C2: vendor visibility is metadata-first, not tenant-business-data-first — §5
Q9, ADR-BOS-009). Not part of the frozen ADR set. · Date: 26.07.2026, §10 added
27.07.2026 (vendor session observability + mandatory audit correlation,
migration 0013 — a hardening follow-up to phase 1, §9, ahead of Company
Provisioning), §11 added 27.07.2026 (Company Provisioning Foundation — phase
2 done: atomic `ProvisionCompany`, migration 0014, identity's first write
contract), §12 added 27.07.2026 (Entitlement Management — phase 3 done:
grant/revoke module entitlement routes, no migration, no new import-linter
contract), §13 added 27.07.2026 (Subscription Lifecycle Transitions — phase
4 done: reasoned state transitions, `require_subscription_ok` wired onto
professional_services only by explicit scope decision, platform-wide
retrofit deferred) · Source: PO directive accepting the frozen product model
(Business OS + sibling apps + RepairFlow business profiles); read-only audit
of the repository as it stands after the PropertyFlow dashboard slice
(`frontend/src/ps/`, uncommitted at audit time — see §8).

This document is the audit trail and the answer key. The actual decisions are
in four new ADRs it cross-references (ADR-BOS-009…012); this document exists
so those decisions have one place that shows the evidence they were built on
and the questions they collectively answer.

## 1. Phase 1 — Read-only audit findings

### 1.1 Tenant/company model

- `companies` (`business_os/identity/models.py`) is the tenant: `id`,
  `name`, `requisites` (JSONB), `vat_registered`, `settings` (JSONB). One row
  per paying business (ADR-013).
- Isolation: three layers per ADR-016 — server-derived `TenantContext`
  (never client-supplied), a scoped-query chokepoint (`shared_kernel.db`),
  and PostgreSQL RLS (`FORCE ROW LEVEL SECURITY`, fail-closed GUC). The app
  DB role is non-superuser by deployment requirement (superusers bypass
  RLS). `companies`/`users`/`sessions`/`audit_log` are RLS-**exempt**
  (identity bootstrap — no `company_id` to scope by, for `companies` itself)
  with queries centralized in `identity.service` as the compensating
  control.
- **Vendor-created tenants**: the only code path that creates a company is
  `identity.service.seed_company`, called exclusively from
  `serviceflow/seed.py` — a CLI script run by hand
  (`uv run python -m serviceflow.seed "Name" "Owner" email password`). No
  HTTP endpoint creates a company. This satisfies "vendor-only creation" by
  omission (nobody else can either), not by a designed control.
  Self-service registration is documented (docs/13 Етап 3: "company
  self-registration, email verification, ≤3-step wizard") but **not built**.
- **Company creation today is: CLI-only.** Not public, not self-service, not
  admin-UI — a maintainer/ops action.

### 1.2 Identity and roles

- One role bit: `User.is_owner: bool`. `TenantContext` carries
  `(company_id, user_id, is_owner)` — nothing else.
- First Owner: created by the same `seed_company` call that creates the
  company (one User row with `is_owner=True`), never separately.
- **A company Owner cannot create employees today.** `users_router` exposes
  only `GET /users` (list). The router's own comment says it plainly:
  "POST/PATCH/deactivate са Етап 3 (администрация)." There is no
  employee-invite flow of any kind yet.
- **No platform/vendor admin role exists anywhere in code** — confirmed by
  exhaustive grep (`vendor`, `platform_admin`, `PlatformAdmin`,
  `is_platform_admin`) across `backend/src`: zero matches outside this
  audit's own new files.
- Platform and tenant roles are therefore **not mixed** — there is nothing
  to un-mix. The risk is prospective: whatever role concept is added next
  must not be bolted onto `users.is_owner` (see ADR-BOS-009).
- `require_owner` (the one owner-gate dependency) currently guards exactly
  one endpoint: `POST /customers/{id}/anonymize` (GDPR anonymization).

### 1.3 Module activation

- Stored at `companies.settings.active_modules` (JSONB string list) —
  `identity.service.is_module_active` / `.active_modules` /
  `.activate_module`.
- **Who can change it today: nobody, via the app.** `activate_module`'s only
  caller in the entire backend is `serviceflow/seed.py`. Grepped and
  confirmed — no router, no service, no test outside the identity/seed
  layer calls it.
- Enforcement is real and correctly layered:
  - **Backend**: `professional_services.deps.require_ps_active` — a
    request-scoped dependency mounted on the whole PS router
    (`dependencies=[Depends(require_ps_active)]`) that raises 404 with
    `message_key: errors.ps.module_inactive` when inactive. This is the
    template for every future module.
  - **Frontend**: `AppShell.APPS` filters the app-switcher/nav by
    `me.active_modules` (from `GET /auth/me`'s `active_modules` field). This
    is a UX courtesy layered *on top of* the backend 404 — removing it would
    not expose data, only a dead nav entry.
- **Entitlement (may-use-at-all) and configuration (feature behavior inside
  an entitled module) are already conceptually distinct in the one module
  that exists** (PS workflow templates, stage config are tenant-owned
  *inside* an entitled module) — this audit's job is to keep that line
  explicit as more modules and a real activation UI arrive (ADR-BOS-010).

### 1.4 Licensing/subscriptions

- ADR-009 (local-edition offline license tokens) is **Superseded** by
  ADR-018 (SaaS subscriptions) per the 11.07.2026 pivot; ADR-018 itself is
  **Accepted** but **0% implemented**: no `PaymentProvider` port, no webhook
  inbox table, no subscription-state column, no trial logic, anywhere in
  `backend/src`. Confirmed by grep (`subscription`, `billing`, `webhook`,
  `trial`) — zero implementation hits.
- docs/13 (Implementation Plan) already schedules "Абонаменти и billing
  (ADR-018)" and "Платформена админ конзола (vendor)" inside **Етап 3**,
  not yet started.
- **No seat/max-users limit exists anywhere** — not in code, not in any
  document before this one. Genuinely new (ADR-BOS-009's ownership matrix,
  §V1 Console scope below).
- Subscription state is **only planned**, nowhere persisted.

### 1.5 RepairFlow profiles

- `AssetType` (`serviceflow/assets/models.py`) is a **global** seed table:
  `code` is a bare primary key (no `company_id`), `field_defs` JSONB is
  identical for every tenant, seeded once by migration 0003 (`phone`,
  `vehicle`, `laptop`, `other`).
- Field definitions and validation (`assets/service.py::validate_field_values`)
  already vary *by asset type*, not by company — the mechanism (a typed
  `{key, label_bg, type, choices?, identifier_kind?}` registry, validated
  strictly server-side) is exactly right, it just has no per-company axis.
- The codebase already has a directly reusable precedent for
  "registry-as-data, reviewed like code": `modules/construction-supervision`'s
  ADR-CS-007 (document types as registry rows, not hard-coded classes) and
  this repo's own docs/08 §4 standing rejection of a generic EAV/custom-fields
  platform. Both point the same direction: extend the existing typed-JSONB
  pattern with a company scope, do not invent a second mechanism.
- **Risk of adding `business_profile` to `companies.settings` vs. a
  dedicated domain model**: settings-JSONB is right for the *assignment
  record* (which profile a company was assigned — one string, no relations,
  matches the existing settings pattern exactly). It is **wrong** for the
  asset-type rows themselves, which need real per-company existence (a
  company must be able to have its *own* copy of "vehicle" with its *own*
  field set, independently of another company's copy) — that needs
  `asset_types` to become company-scoped data, not a JSONB blob describing
  types. See ADR-BOS-011 for the resolution (settings key for the
  assignment, scoped table for the types) and §6 below for the schema shape.
  **One caveat introduced by PO clarification 1** (vendor-assigned, not
  tenant-chosen): storing the assignment inside `companies.settings` — a
  blob the tenant otherwise owns and will eventually edit through a
  settings UI — means the *write path* must be guarded specifically, not
  just the value's presence. A future generic "PATCH company settings"
  tenant endpoint must not be able to write the `repairflow.business_profile`
  key. Either the guard is explicit (key allow-list on the tenant settings
  endpoint) or the assignment moves to its own vendor-owned column; decide
  at implementation time, but do not let the JSONB convenience quietly
  re-grant the tenant a capability this clarification removed.

### 1.6 Administration UI

- Company settings / user-management screens: **do not exist**. `AppShell`'s
  sidebar has a permanently greyed "Настройки" nav item
  (`GrayedNavItem`, tooltip "Очаквайте скоро") — a placeholder, no route
  behind it.
- No vendor admin screen or vendor admin concept exists in the frontend —
  confirmed by an exhaustive filename search (`*settings*`, `*admin*`,
  `*vendor*` under `frontend/src`): zero matches.
- `AppShell` assumes exactly one kind of authenticated user (a tenant
  session) throughout — `useAuth()`'s `Me` shape has no room for a
  vendor-admin session, which is the correct current state (see
  ADR-BOS-009: they must stay structurally separate, not "extend `Me`").
- **No route or API exposes cross-tenant data.** Every router either takes
  `TenantDep`/`TenantDbDep` (scoped to the caller's own company) or nothing
  tenant-shaped at all (`/auth/login`, `/platform/health`). There is no
  `GET /companies` anywhere. This is a clean starting point, not a gap to
  fix.

### 1.7 Documentation inventory (needs updates)

| Document | What needs updating | Status after this audit |
|---|---|---|
| `docs/adr/` | New ADRs for the vendor/tenant split | **Done** — ADR-BOS-009…012 added |
| `docs/business-os/17_BUSINESS_CAPABILITIES_MATRIX.md` | Add Vendor Control Plane, RepairFlow business profiles rows | Updated same session |
| `docs/business-os/05_DATA_OWNERSHIP.md` | Add planned tables: `platform_admins`, `platform_audit_log`, subscription state, scoped `asset_types` | Updated same session |
| `docs/business-os/08_EVOLUTION_ROADMAP.md` | Break out Vendor Console / entitlements / profiles as named workstreams | Updated same session |
| `docs/business-os/10_GLOSSARY.md` | Vendor Administrator, Tenant Owner, Tenant Employee, Entitlement, Business Profile, Vendor Control Plane, Tenant Workspace | Updated same session |
| `docs/13_IMPLEMENTATION_PLAN.md` (Етап 3) | Cross-reference the new ADRs from the existing "Платформена админ конзола" / "Администрация (tenant)" bullets | Updated same session |
| `docs/11_SECURITY_MODEL.md` | Already self-flagged stale for SaaS (§ header); this audit adds vendor/tenant role separation as a named future §2 item without doing the full rewrite the header already schedules for Етап 3 | Updated same session (pointer only) |
| `docs/09_API_SPECIFICATION.md` | Will need the Vendor Control Plane's endpoint contracts | **Not touched** — no endpoints exist yet to specify; do this when ADR-BOS-009's console is actually built, not speculatively now |
| Threat model (`docs/11 §1`) | Add cross-tenant vendor-console access, vendor-credential compromise | **Not rewritten** — already an explicit, scheduled Етап-3 task; this audit does not duplicate it early |
| `modules/professional-services/docs/28_BUSINESS_OS_INTEGRATION.md` | Cross-check its own module-activation assumptions still match ADR-BOS-010 | **Checked, consistent** — PS already does the right thing (`require_ps_active`); no changes needed |

### 1.8 Security and auditability

- **Required audit events for vendor actions**: company create, first-Owner
  create, entitlement grant/revoke, subscription-state transition, seat-limit
  change, suspend/reactivate, business-profile assignment — all defined as
  the `platform_audit_log` shape in ADR-BOS-009 §Decision. None exist today
  because no vendor actions exist today.
- **Cross-tenant access risk**: currently minimal by absence — no code path
  reads across tenants at all (RLS would block it even if a query forgot to
  scope; the isolation test suite, P0-9, already proves this for every
  existing tenant table). The risk is entirely prospective: it activates the
  moment a Vendor Control Plane router exists and must read across
  companies *by design* — which is exactly why ADR-BOS-009 requires those
  reads to be explicit, path-parameterized, and audited rather than an
  implicit "RLS-exempt because it's Core" shortcut.
- **Vendor support impersonation**: not implemented, not designed beyond
  ADR-BOS-009's explicit exclusion ("a separate, explicitly
  security-reviewed feature"). Out of scope for V1 per this task's own
  constraints.
- **Stronger authentication for sensitive vendor actions**: not decided by
  this audit — flagged as an open question for the Vendor Console's own
  design pass (candidate: re-auth/step-up for suspend/entitlement-revoke,
  same class of control as `require_owner` today but for the vendor plane).
  Not blocking V1 Vendor Console scope (§7), but should be resolved before
  that console handles real paying customers.
- **Tenant deletion**: no delete path exists for `companies` anywhere in
  code today (confirmed by grep — no `DELETE`/drop-company code). This
  already matches the desired model (suspend/archive, never hard-delete);
  ADR-BOS-012's `cancelled` state is explicitly non-destructive (data
  retained, same as module deactivation per ADR-BOS-004 §Decision).

## 2. Gaps between current architecture and the accepted model

| Accepted-model requirement | Current state | Gap |
|---|---|---|
| Vendor administers companies, entitlements, subscriptions, seats | None of this is reachable via the app | Full gap — Vendor Console does not exist (ADR-BOS-009, §7 below) |
| Tenant Owner administers own employees, roles | `GET /users` only, no create/invite | Full gap — tenant admin UI is Етап 3, unchanged by this audit |
| Tenant Owner cannot activate paid apps without vendor approval | Nobody can activate anything via the app | **No gap today** (trivially satisfied by absence); becomes a real requirement the day entitlement mutation is exposed at all — ADR-BOS-010 fixes the target before that day arrives |
| RepairFlow business profiles configure asset behavior per company; vendor assigns at provisioning, tenant configures within, changes after data are controlled migrations | `asset_types` is global, no profile concept, no provisioning flow, no compatibility-review concept | Full gap — ADR-BOS-011; needs a migration (§6.4) plus the vendor provisioning action (§7 screen 3) and the tenant read-only view, none authored here |
| Vendor and tenant roles structurally separate | Only one role (`is_owner`) exists; nothing to conflate yet | **No current violation**, but the natural next step (a boolean on `users`) would create one — ADR-BOS-009 heads this off before it's written |
| Vendor actions audited | No vendor actions exist to audit | Full gap — `platform_audit_log`, proposed not built (§6) |
| Suspension ≠ deletion | No deletion path exists at all | **Already satisfied** |
| Entitlement checks server-side | True for the one module that exists (PS) | **Already satisfied** — restate as the mandatory pattern for module #2+ (ADR-BOS-010) |

## 3. ADRs created

- [ADR-BOS-009](../adr/ADR-BOS-009-vendor-control-plane-vs-tenant-workspace.md) — Vendor Control Plane vs Tenant Workspace
- [ADR-BOS-010](../adr/ADR-BOS-010-application-entitlement-ownership.md) — Application Entitlement Ownership
- [ADR-BOS-011](../adr/ADR-BOS-011-repairflow-business-profiles.md) — RepairFlow Business Profiles
- [ADR-BOS-012](../adr/ADR-BOS-012-subscription-lifecycle-v1-manual.md) — Subscription/Licence Lifecycle (V1, Manually Managed)

## 4. Documentation updated

See §1.7 table. In the same session: `docs/adr/ADR-BOS-009…012` (new),
`docs/business-os/17_BUSINESS_CAPABILITIES_MATRIX.md`,
`docs/business-os/05_DATA_OWNERSHIP.md`,
`docs/business-os/08_EVOLUTION_ROADMAP.md`,
`docs/business-os/10_GLOSSARY.md`, `docs/13_IMPLEMENTATION_PLAN.md`,
`docs/11_SECURITY_MODEL.md`, this document.

## 5. Final ownership matrix

Answers the twelve questions this task set out to resolve explicitly:

| # | Question | Answer |
|---|---|---|
| 1 | Who creates a new customer company? | **Vendor Administrator**, via the future Vendor Control Plane (today: CLI/seed only — same actor category, no UI yet). Never self-service in this task's scope (ADR-018's future self-registration is separate, untouched). |
| 2 | Who creates the first Owner? | **Vendor Administrator**, atomically with company creation (unchanged from today's `seed_company` shape — one call creates both). |
| 3 | Who creates employees? | **Tenant Owner**, within their own company, bounded by the vendor-set seat limit. Not built yet (docs/13 Étап 3); ownership is settled, UI is future work. |
| 4 | Who activates RepairFlow or PropertyFlow? | **Vendor Administrator only** (ADR-BOS-010). A Tenant Owner can never self-activate a module, paid or not. |
| 5 | Who sets the business profile? | **Vendor Administrator assigns it during company provisioning** (PO clarification 1, 26.07.2026 — ADR-BOS-011 §Decision 3). The **Tenant Owner configures workflows, templates and application settings *inside* the assigned profile** freely, but cannot switch the profile itself; they may *request* a change. Changing a profile once assets/orders exist is a **controlled migration** requiring compatibility review and vendor approval (ADR-BOS-011 §Decision 7). A profile is **not** an entitlement (ADR-BOS-010 owns that) and **not** an ordinary tenant preference. |
| 6 | Who controls maximum seats? | **Vendor Administrator** sets the limit; **Tenant Owner** operates within it (cannot exceed it when inviting employees) but cannot raise it. |
| 7 | What happens when the subscription expires? | Transitions to `grace_period` then `suspended` (ADR-BOS-012) — full data visibility, export/backup always available, mutations blocked with a plain explanation (ADR-009 philosophy, carried through ADR-018 and this ADR unchanged). Data is never deleted. |
| 8 | What can a tenant Owner see but not modify? | Vendor-controlled facts about their own company: which modules are entitled, subscription state, seat limit, **and the assigned RepairFlow business profile** (read-only, with a "request a change" affordance — never a selector). Vendor internal notes are not shown at all, not even read-only — they are vendor-internal by definition. |
| 9 | What can a vendor administrator see across tenants? | **Administrative metadata only — "vendor visibility is metadata-first, not tenant-business-data-first"** (PO clarification 2, 26.07.2026 — ADR-BOS-009 §Vendor data visibility). **Visible:** company identity, subscription/licence status, activated applications, seat limit + usage, business profile, suspension status, deployment/version/health metadata, internal support notes, platform audit history. **Not visible:** customers, assets, service orders, engagements, documents, invoices/transactions, and notes belonging to the customer company. Aggregate counts over those are metadata and stay visible; individual rows do not. Future support access to operational data must be separately designed, explicitly authorised, time-bounded where practical, strongly audited — and is **out of scope for the V1 Vendor Console**. |
| 10 | How are vendor actions audited? | `platform_audit_log` (proposed, §6): actor, target company, action, reason, timestamp, append-only — same reasoned-change discipline `PSDeadlineChange` already established. |
| 11 | Is the Vendor Console included in tenant navigation? | **No, never.** Separate route namespace (`/vendor/*`), never linked from `AppShell`, never reachable from a tenant session (ADR-BOS-009 §Decision — structurally separate sessions, not just hidden nav). |
| 12 | Is business profile the same as module activation? | **No — and this stays true after clarification 1, which changed *who assigns* the profile, not *what it is*.** Module activation/entitlement = "**does** this company have RepairFlow at all" (vendor-controlled, ADR-BOS-010). Business profile = "**how** does RepairFlow behave for this company" (vendor-*assigned* at provisioning, tenant-*configured* within, RepairFlow-scoped, ADR-BOS-011). Both are now vendor-assigned, which makes the distinction *more* important to state, not less: entitling RepairFlow never implies a profile, assigning a profile never grants an entitlement, and they are stored, audited and changed independently. Conflating them is the exact anti-pattern ADR-BOS-010 §4 and ADR-BOS-011 §Decision 1 both call out by name. |

### Ownership matrix — actions

| Action | Vendor Administrator | Tenant Owner | Tenant Employee |
|---|---|---|---|
| Create company / first Owner | ✅ | ❌ | ❌ |
| Grant/revoke module entitlement | ✅ | ❌ | ❌ |
| Set subscription state | ✅ | ❌ | ❌ |
| Set seat limit | ✅ | ❌ | ❌ |
| Suspend/reactivate company | ✅ | ❌ | ❌ |
| Create/invite employees (within seat limit) | ❌ | ✅ | ❌ |
| **Assign** initial RepairFlow business profile (at provisioning) | ✅ | ❌ | ❌ |
| **Change** business profile after operational data exists | ✅ (on tenant request, after compatibility review + approval) | ❌ — may **request** only | ❌ |
| View assigned business profile | ✅ | ✅ (read-only) | ✅ (read-only) |
| Configure workflow templates/statuses/warranty defaults **within** the assigned profile | ❌ | ✅ | per future permission (today: none exist beyond Owner) |
| List/browse other companies | ✅ (Control Plane only) | ❌ | ❌ |
| See own company's audit trail | ❌ (vendor's `platform_audit_log` is a separate record; vendor internal notes stay vendor-only) | ✅ | ❌ |
| Read cross-tenant administrative **metadata** (identity, subscription, entitlements, seats, profile, suspension, health/version, support notes, platform audit) | ✅ | ❌ | ❌ |
| Read tenant **operational data** (customers, assets, orders, engagements, documents, invoices/transactions, customer-authored notes) | ❌ — aggregate counts only | ✅ | ✅ (same as Owner today — no finer read-permission exists yet) |

## 6. Recommended data model changes (not implemented — approval required before any migration)

Per this task's Phase 4 rule, none of the following are built. Each is
proposed here with rationale, shape, compatibility impact, and rollback
strategy, for explicit approval before a migration is authored.

### 6.1 `platform_admins` (Core, new table)

- **Why now**: ADR-BOS-009 requires vendor identity to be structurally
  separate from `users`; no existing table can hold it without violating
  that separation.
- **Proposed schema**: `id uuid pk`, `name text`, `email text unique`,
  `password_hash text`, `is_active bool default true`, `created_at`,
  `updated_at`. No `company_id` — RLS-exempt by construction, same
  compensating-control discipline as `companies`/`users`.
- **Compatibility impact**: additive only, zero impact on existing tables or
  queries.
- **Rollback**: drop table; nothing references it yet.

### 6.2 `platform_audit_log` (Core, new table)

- **Why now**: ADR-BOS-009 §Decision requires vendor mutations audited; the
  existing `audit_log`'s `user_id` FK is typed to `users.id`, incompatible
  with a `platform_admins.id` actor without a dual-typed column.
- **Proposed schema**: `id uuid pk`, `platform_admin_id uuid fk
  platform_admins.id`, `company_id uuid fk companies.id nullable` (nullable
  for actions with no single target, e.g. a companies-list view logged for
  security review), `action text`, `detail jsonb default '{}'`, `reason
  text nullable`, `created_at`.
- **Compatibility impact**: additive only.
- **Rollback**: drop table.

### 6.3 Subscription state on `companies` (or a sibling table)

- **Why now**: ADR-BOS-012 needs somewhere to persist
  `trial|active|grace_period|suspended|cancelled` plus the dates that drive
  it.
- **Proposed shape (two options, decide at implementation time)**:
  (a) columns directly on `companies` — `subscription_state text`,
  `subscription_state_changed_at timestamptz`, `trial_ends_at
  timestamptz nullable`, `seat_limit int nullable` (nullable = unlimited,
  a deliberate escape hatch for the vendor's own test/demo companies); or
  (b) a `company_subscriptions` sibling table (1:1 with `companies`) if the
  column count grows once ADR-018's provider fields (customer id, plan id)
  eventually land — **recommend (a) for V1** (fewer moving parts, matches
  `companies.settings`-adjacent precedent) with an explicit note that (b)
  is the natural migration target when ADR-018's provider integration
  starts, not before.
- **Compatibility impact**: additive columns on an existing table — every
  current company needs a backfill default (`subscription_state = 'active'`
  for all pre-existing seeded companies, so nothing currently running
  degrades on migration day).
- **Rollback**: drop columns; no other table references them.

### 6.4 Company-scoped `asset_types` (RepairFlow, schema change to an existing table)

- **Why now**: ADR-BOS-011 requires per-company asset-type rows; today's
  `code`-only primary key structurally cannot express two companies with
  different definitions of "vehicle."
- **Proposed schema**: add `company_id uuid fk companies.id` to
  `asset_types`; primary key becomes `(company_id, code)` (or a new
  UUIDv7 `id` with a unique `(company_id, code)` constraint, consistent
  with ADR-013's "every domain record carries a UUIDv7 id" — **recommend
  the UUIDv7-id form** to match the rest of the schema rather than a
  composite key, which nothing else in this codebase uses). Add RLS
  (`FORCE ROW LEVEL SECURITY`, the standard tenant policy) — `asset_types`
  moves from RLS-exempt (it isn't currently RLS'd because it's global
  reference data) to a normal tenant table.
- **Backfill**: every existing company gets its own copy of today's four
  types (`phone`, `vehicle`, `laptop`, `other`) with today's exact
  `field_defs`, tagged `business_profile = generic_repair` — behavior-
  identical to today for every current tenant.
- **Compatibility impact**: **real** — `assets.asset_type_code` currently
  FKs to a global `asset_types.code`; that FK needs to become
  company-aware (either compound FK or resolved via the new `id`). This
  touches `assets/models.py`, `assets/service.py`, `assets/router.py`, and
  every test/fixture that references a bare asset-type code. The largest of
  the four proposed changes — should land as its own reviewed migration PR,
  not bundled with §6.1–6.3.
- **Rollback**: non-trivial once any company has a second profile's asset
  types — plan the migration as additive-first (new scoped table populated
  alongside the old global one, cut over reads, then drop the global table
  in a second migration) rather than an in-place ALTER, so each step is
  independently reversible.

## 7. V1 Vendor Console — documented scope only (nothing built)

Ten screens, matching the task's own enumeration, each mapped to the ADR
that governs it:

1. **Companies list** — ADR-BOS-009 (Control Plane read)
2. **Company details** — ADR-BOS-009
3. **Create company** — ADR-BOS-009 §Decision (Vendor Administrator only).
   Per clarification 1, **assigning the initial RepairFlow business profile
   is part of this action**, not an optional follow-up: a company cannot be
   provisioned without one (`generic_repair` is the explicit default).
4. **Create first Owner** — ADR-BOS-009, same action as #3 in practice
5. **Activated applications** — ADR-BOS-010 (entitlement grant/revoke)
6. **RepairFlow business profile** — ADR-BOS-011 §Decision 3. Per PO
   clarification 1 this is a **vendor-owned assignment**, so the console is
   the *primary* place it is set: chosen during company provisioning
   (screen 3) and changeable afterwards only through the controlled path
   (tenant request → compatibility review → vendor approval → audited
   change). The tenant-side settings UI shows it read-only. This screen
   therefore needs both the assignment control and the compatibility-review
   view that must precede any post-data change.
7. **Subscription/licence dates and status** — ADR-BOS-012
8. **Seat limit and current usage** — ADR-BOS-009 ownership matrix row 6;
   "current usage" reads the tenant's own `users` count, read-only from the
   vendor side
9. **Suspend/reactivate company** — ADR-BOS-012 state transitions
10. **Internal notes and audit history** — ADR-BOS-009 §Decision
    (`platform_audit_log`); internal notes are vendor-only, never surfaced
    to any tenant role (ownership matrix, §5)

**Out of scope for V1** (restated from the task, unchanged, binding): automated
card billing, payment gateway integration, tax invoices for the subscription
itself, customer self-service purchase, marketplace, usage-based billing,
complex plan catalogue, vendor impersonation (unless separately security
reviewed), hard tenant deletion, generic no-code profile builder.

## 8. Testing strategy — required future tests

None of these exist yet (nothing to test — no code built). Documented so the
Vendor Console's first PR ships with them, not after:

- Vendor admin can create a company (+ its first Owner, atomically).
- Vendor admin can assign/revoke module entitlements; the change is visible
  via `GET /auth/me`'s `active_modules` on the tenant's next request.
- **Tenant Owner cannot assign entitlements** — a negative test hitting
  whatever entitlement-mutation endpoint exists with a tenant session,
  expecting 403/404, never 200. (Mirrors the isolation-suite discipline
  ADR-016's P0-9 already established for cross-tenant reads — same rigor,
  applied to cross-plane writes.)
- Vendor admin can set a seat limit.
- Tenant Owner cannot exceed the seat limit when creating employees
  (boundary test: exactly at the limit succeeds, one over fails with a
  clear message_key).
- Tenant Owner can create employees within the limit.
- A `suspended` company's protected endpoints reject mutations
  (`require_subscription_ok`) while reads/export continue to succeed —
  both halves of ADR-009/018's degradation promise, tested explicitly, not
  assumed.
- One tenant cannot access another tenant's data via any Vendor Control
  Plane code path either (extends the existing isolation suite to the new
  plane — a vendor-scoped query that forgets to take `company_id` as an
  explicit parameter must still be impossible to coerce into leaking a
  second company's rows).
- RepairFlow business profile controls which asset types/fields are
  accepted (positive: profile's own types validate; negative: a field not
  in the active profile is rejected server-side even if sent directly to
  the API, bypassing the frontend).
- **A vendor administrator can assign a business profile during company
  provisioning**, and a company cannot be created without one (default
  `generic_repair` applied when unspecified).
- **A Tenant Owner cannot change the business profile** — negative test:
  any tenant-session attempt at the profile-change path returns 403/404,
  never 200. (Same shape as the entitlement negative test above; both are
  cross-plane write attempts.)
- **A profile change after operational data exists requires the controlled
  path** — a vendor-initiated change against a company that already has
  assets/orders is rejected unless the compatibility review has been
  performed and approval recorded; the resulting change writes a
  `platform_audit_log` row carrying the review outcome and reason.
- Changing a company's business profile does not corrupt/drop existing
  assets' `field_values` (regression test: create an asset under profile A,
  change to profile B via the controlled path, re-fetch the asset, assert
  its stored values are byte-identical and the asset still renders).
- **Vendor metadata/operational-data boundary** (clarification 2): a
  vendor-session request can read a company's administrative metadata
  (identity, subscription, entitlements, seat usage, profile, suspension,
  audit history) **and** aggregate counts, but every attempt to read
  individual tenant operational rows — customers, assets, orders,
  engagements, documents, invoices, contact notes — fails. Tested per
  entity family, not once generically, so a future endpoint that forgets
  the rule fails a named test rather than slipping through.
- **A vendor session yields no `TenantContext`** — a structural test that
  the two session kinds cannot cross-resolve in either direction
  (complements the endpoint-level tests above by proving the mechanism,
  not just its current call sites).
- Every vendor mutation (entitlement change, subscription transition, seat
  limit change, suspend/reactivate, company create) produces exactly one
  `platform_audit_log` row with the correct actor/target/action/reason.

## 9. Recommended implementation phases and commits

Sequenced so each phase ships independently and reversibly, per this
project's existing ratchet discipline (docs/business-os/08 Phase 1/2
precedent):

1. **Vendor Control Plane foundation** — `platform_admins` +
   `platform_audit_log` migrations (§6.1/6.2), vendor session kind,
   `require_platform_admin` dependency, empty console shell (companies list
   + details, read-only). No entitlement/subscription mutation yet.
   *Commit shape:* `feat(business-os): add vendor control plane foundation`.
2. **Company provisioning — Done (27.07.2026), see §11.** Atomic
   `ProvisionCompany` command (company + first Owner + initial RepairFlow
   profile + initial entitlements + subscription trial baseline + one audit
   row, one transaction) plus read-only `GET /companies`/`GET
   /companies/{id}`. Pulled forward from phase 4 below: the
   `subscription_state`/`trial_ends_at`/`seat_limit`/
   `subscription_state_changed_at` columns (§6.3) were needed for the
   baseline this phase sets, so migration 0014 built them now rather than
   waiting. What phase 4 still owes: `require_subscription_ok` and the
   *transition* screens (suspend/reactivate/grace period) — this phase only
   ever writes `'trial'`, once, at creation.
   *Commit:* `feat(business-os): add company provisioning foundation`.
3. **Entitlement management — Done (27.07.2026), see §12.** `PUT`/`DELETE
   /companies/{id}/modules/{module_key}`, wired to the existing
   `activate_module`/`is_module_active` machinery via new symmetric
   `identity.contracts.grant_module`/`revoke_module` — *editing* entitlements
   after provisioning, distinct from the initial grant phase 2 (§11) already
   covers. `require_ps_active` (ADR-BOS-010 §Decision 2) is unchanged;
   proven end-to-end that the new audited path actually flips what it reads.
   *Commit:* `feat(business-os): vendor-managed module entitlements`.
4. **Manually managed V1 subscriptions — Done (27.07.2026), see §13.**
   `POST /companies/{id}/subscription/transitions` (one endpoint, any state,
   mandatory reason — console #7/#9's suspend/reactivate buttons are just
   this call with a different `new_state`) plus `require_subscription_ok`,
   wired onto `professional_services`' own mutating routes only (explicit
   scope decision — not a platform-wide retrofit in this slice; see §13.3).
   *Commit:* `feat(business-os): add subscription lifecycle transitions`.
5. **Seat limits** — column + enforcement on the (still-unbuilt) employee
   creation endpoint; console screen #8.
   *Commit:* `feat(business-os): seat limit enforcement`.
6. **RepairFlow business profiles** — the §6.4 migration (its own PR, largest
   of the set), profile selector in tenant settings, backend field-def
   resolution switched from global to company-scoped.
   *Commit:* `feat(repairflow): company-scoped business profiles (ADR-BOS-011)`.
7. **Tenant user management** — the employee invite/deactivate flow docs/13
   Étап 3 already scheduled, now bounded by seat limits from phase 5.
   *Commit:* `feat(business-os): tenant employee management`.
8. **Security/audit hardening** — the §8 test suite in full, the Étап-3
   threat-model rewrite docs/11 already schedules, extended for the new
   plane.
   *Commit:* `test(business-os): vendor/tenant isolation + audit suite`.
9. **Optional, later**: ADR-018's automated billing, superseding phase 4's
   manual transitions one trigger at a time (webhook replaces vendor click,
   nothing else changes per ADR-BOS-012 §Consequences).

Each phase is independently shippable and none blocks ServiceFlow/PropertyFlow
product work, matching the standing governing constraint (docs/business-os/08
§Governing constraints: "Business OS phases interleave with Étап 2–5; none of
them may delay or destabilize a stage").

## 10. Vendor session observability & audit correlation (hardening, 27.07.2026)

A narrow follow-up to phase 1 (§9), landed before Company Provisioning
(migration 0013). Two independent additions, both to the tables phase 1
already introduced — no new tables, no schema change to anything tenant-owned.

### 10.1 Session metadata — what is stored, what deliberately is not

`platform_admin_sessions` gained two nullable columns, in preparation for a
future "active sessions" / "revoke another session" screen (not built by this
hardening pass):

- **`user_agent`** — captured verbatim from the HTTP `User-Agent` header at
  login, bounded to 300 characters
  (`platform_admin.service.MAX_USER_AGENT_LENGTH`). Diagnostic only: never
  read for authentication or authorization, never updated after login (a
  session doesn't change browsers mid-life).
- **`client_label`** — reserved for a future user-assigned name ("Office
  PC", "Laptop"). Nullable, unused by any code path in this slice, and
  **never auto-populated from `user_agent`** — inventing a device identity
  from a header string would misrepresent something nobody confirmed.

**Deliberately not stored**: IP address, precise geolocation, browser
fingerprinting beyond the raw `User-Agent` string, or the raw session token
itself. IP address in particular was considered and rejected for this slice —
there is no concrete support/security workflow that needs it yet, and adding
it later requires its own documented retention policy (how long kept, who may
read it, GDPR posture per docs/11 §6) rather than being smuggled in as a side
effect of a session-metadata column.

**`last_seen_at`** (added by phase 1, migration 0012) already existed and was
already written unconditionally on every authenticated request — found during
this hardening pass's audit as exactly the write-amplification pattern this
document warns against for new fields. Fixed in the same slice: it now updates
only when more than `LAST_SEEN_UPDATE_INTERVAL` (1 minute) has elapsed since
the last write, cutting the per-request DB round trip to roughly once per
minute of activity instead of once per request.

### 10.2 Request correlation — design and propagation

`business_os.shared_kernel.correlation` (neutral, like `passwords.py` — used
by both the tenant application and the vendor plane, so it cannot live in
either):

- every HTTP request (tenant and vendor alike — the middleware in
  `serviceflow/main.py` is global) is bound to a freshly **server-generated**
  UUID4 for its duration, via a `contextvars.ContextVar`;
- returned in the `X-Request-ID` response header;
- attached to every application log line through a `logging.Filter`
  (`CorrelationLogFilter`), closing a pre-existing gap where the log
  formatter already supported a `request_id` field but nothing ever
  populated it;
- persisted as `platform_audit_log.request_id` (migration 0013, `NOT NULL`)
  for every vendor audit row, via `platform_admin.audit.record()`'s
  mandatory `request_id` parameter — there is no code path that writes a
  vendor audit row without one;
- CLI/background operations are not HTTP requests, so they bind their own
  id at their own entry point (`business_os.platform_admin.bootstrap.main()`
  calls `correlation.bind()` before doing anything else) — the same
  contextvar mechanism, a different boundary.

**A previously-incoming `X-Request-ID` header is never adopted.** The
pre-hardening middleware accepted any client-supplied value verbatim, with no
length bound or format check — audited and found to be exactly the "already
follows the convention AND validates it" condition failing, so the value is
now always freshly generated server-side regardless of what a caller sends.
This is a deliberate, documented policy choice, not an oversight: a client
cannot inject an arbitrary string into application logs or the audit trail
merely by setting a header, and no correlation id is ever treated as unique
because a client supplied it. If a genuine need for validated cross-service
trace propagation arises later, it should be added as its own reviewed
decision (a strict allow-list pattern, a bound length), not by reverting to
the old blind pass-through.

**Correlation ids are observability data, not security credentials.** They
are never checked for authorization, never used to resolve a session or a
`TenantContext`, and their presence or value has no bearing on what a request
is permitted to do — only on how it can be found in logs and the audit trail
after the fact.

## 11. Company Provisioning Foundation (phase 2, 27.07.2026)

### 11.1 Provisioning as a domain command

`business_os.platform_admin.service.provision_company()` is the **only**
supported orchestration entry point for creating a company. Future vendor
features — wizard UI, CLI, import tools, reseller APIs, marketplace
onboarding, automated signup — must all call it; none may assemble their own
create-company/create-owner/assign-modules sequence. This is enforced by a
naming-convention test
(`tests/test_company_provisioning.py::test_provision_company_is_the_only_public_write_entry_point_in_its_module`),
not by an import-linter contract — there is exactly one module
(`platform_admin.service`) where a second orchestrator could plausibly
appear, so a grep-shaped test is proportionate; a second package attempting
its own orchestration would already be caught by `vendor-plane-private`
(only `platform_admin` and the composition root may import its internals).

### 11.2 Atomicity

The whole operation — company, first Tenant Owner, RepairFlow profile,
initial entitlements, subscription trial baseline, and exactly one
`platform_audit_log` row — commits **once**, at the end of
`provision_company()`. Every step it composes is deliberately
non-committing:

- `identity.contracts.provision_company` (company + Owner, via
  `identity.service.create_company_with_owner`);
- `identity.contracts.set_business_profile`;
- `identity.contracts.grant_module` (one call per requested module);
- `identity.contracts.set_subscription_trial`.

This was a real risk, not a hypothetical one: `identity.service.seed_company`
and `.activate_module` — the two existing building blocks a naive
implementation would have reached for — each call `db.commit()` internally.
Composing them as-is would not have been atomic: a failure after
`seed_company`'s own commit would have left a company with an Owner but no
profile, entitlements, subscription state, or audit trail. The fix was new
non-committing variants (`create_company_with_owner`,
`_activate_module`/`grant_module`, `set_business_profile`,
`set_subscription_trial`), not a nested transaction/SAVEPOINT — simpler, and
`activate_module` itself was refactored to call the same non-committing
`_activate_module` plus its own commit, so its existing caller
(`serviceflow/seed.py`) is unaffected.

Provisioning is considered successful only if the business data **and** the
audit record commit together — the audit row is part of the operation, not
appended after it. A failure writing the audit row itself (proven in tests
with a foreign-key violation on `platform_admin_id`) rolls back the company
and Owner right along with it.

### 11.3 The new identity write surface

`identity.contracts` — previously read-only (`get_company_profile`,
`is_module_active`) — gained its first write functions:
`provision_company`, `grant_module`, `set_business_profile`,
`set_subscription_trial`, plus two new read functions
(`list_companies_admin_metadata`, `get_company_admin_metadata`) backing the
company list/detail routes. No import-linter contract needed to change:
`identity.contracts` was never in `identity-public-boundary`'s protected list
(only `.models`/`.service`/`.security`/`.router` are), and
`vendor-plane-not-tenant-code` only ever forbade `identity.deps` — this
extension was anticipated when that contract was written (see its comment
in `backend/.importlinter`).

Neither `identity.contracts` nor `identity.service` validates RepairFlow's
profile vocabulary or the module-key registry — that validation
(`platform_admin.service.VALID_BUSINESS_PROFILES`) belongs to the caller
doing the vendor-side assignment (ADR-BOS-011 §Decision 3), the same way
`_activate_module` never validated `module_key` even before provisioning
existed.

### 11.4 Business profile and subscription baseline, scoped precisely

**Business profile** (ADR-BOS-011 §Decision 2): the five-slug identifier is
written to `companies.settings.repairflow.business_profile` — the existing
JSONB-settings mechanism, no new column, no new table. **This is the
identifier only.** The real schema change ADR-BOS-011 §Decision 5 describes
— `asset_types` becoming company-scoped, seeded at profile assignment — is
explicitly **not** part of this slice; it is BOS-18 §6.4's own, separate,
larger migration. A newly provisioned company's asset types remain the
current global set regardless of the profile slug recorded for it, until
§6.4 ships.

**Subscription baseline** (ADR-BOS-012): every company created by
`ProvisionCompany` starts in `trial` with `trial_ends_at` 14 days out
(ADR-018's number, inherited unchanged). Companies created by
`identity.service.seed_company` (the unrelated dev/CLI path) keep defaulting
to `'active'` via the column's `server_default` — that default is
permanent, not a migration-day-only backfill (contrast migration 0013's
`request_id`, whose default was dropped once every writer went through
`audit.record()`), because `seed_company` is a legitimate, continuing
creation path that has no reason to know about subscription states at all.

### 11.5 Vendor-visible metadata (company list/detail)

`GET /companies` and `GET /companies/{id}` return exactly:
id, name, business profile, active modules, subscription state and its
dates, seat limit, created-at. No seat *usage* count (needs a tenant
employee count — out of scope), no tenant operational data, no owner email
or company requisites. `GET /companies/{id}` 404s for a non-existent id,
resolved server-side — existence is never inferred from anything
client-supplied (ADR-BOS-009 §Tenant isolation requirement, restated for the
Control Plane).

### 11.6 `ProvisionResult` — a fixed contract, not a growable response

Follow-up (27.07.2026, same day) to close a gap noticed before Entitlement
Management started: `provision_company()`'s result was already a named
dataclass (`ProvisionCompanyResult`, not a bare tuple), but it was missing
two facts a caller of the command legitimately needs — the computed trial
end date, and a durable reference to the exact audit row this operation
produced. Renamed to `ProvisionResult` and completed to:

```
ProvisionResult
- company_id
- owner_id
- subscription_state
- trial_ends_at
- business_profile
- activated_modules
- audit_id
```

No migration, no new business logic — `trial_ends_at` was already computed
inside `identity.service.set_subscription_trial`, just discarded; it now
returns it (`identity.contracts.set_subscription_trial` too), so
`ProvisionCompany` hands back the exact value it wrote rather than
re-deriving `_now() + timedelta(...)` a second time. `audit_id` required one
real change: `platform_admin.audit.record()` now generates the row's id
explicitly (`shared_kernel.ids.new_id()`) instead of leaving it to the mapped
column's implicit default, so it can return it without an extra flush.

**This is a deliberate boundary**: `ProvisionResult` belongs to the
provisioning contract alone. Entitlement Management (phase 3) and
subscription transitions (phase 4) read and act on a company's *current*
state through the company detail route (§11.5) or their own future
endpoints — neither should grow `ProvisionResult` with fields describing
what happens *after* provisioning, and neither should invent a second,
slightly different result shape next to it.

Note the one intentional naming difference from §11.5: `ProvisionResult.
activated_modules` (what this specific operation just granted) vs.
`CompanyAdminMetadata`/`CompanySummary.active_modules` (the company's full
current set, read fresh from `companies.settings`) — same list in the
common case of a first provisioning call, but a different question, so a
different name.

## 12. Entitlement Management (phase 3, 27.07.2026, ADR-BOS-010)

`PUT`/`DELETE /companies/{company_id}/modules/{module_key}` — grant/revoke
one module entitlement for an already-provisioned company, each its own
atomic vendor operation (existence check, one JSONB mutation, one audit row,
one commit), symmetric to `ProvisionCompany`'s initial grant.

**No new storage, no registry.** Still `companies.settings.active_modules`
(ADR-BOS-010 §Decision 1: the boolean-set shape shipped correctly the first
time); `identity.service._deactivate_module`/`identity.contracts.
revoke_module` are new, symmetric to the existing `_activate_module`/
`grant_module`, equally unvalidating of `module_key` — no registry exists
yet (§Alternatives: deferred until per-module trial/expiry is a real
requirement).

**Idempotent, but never silently unaudited.** Granting an already-active
module (or revoking an already-inactive one) changes nothing —
`EntitlementResult.changed=False` — but still writes an audit row
(`company.module_granted`/`company.module_revoked`, `detail.changed`
records which it was). A vendor action attempted is worth a record even as
a no-op; the alternative (skip the audit write when nothing changed) would
make "did the vendor try this and it was already so" indistinguishable from
"the vendor never tried."

**Independent of subscription state, mechanically, not just by policy**
(ADR-BOS-010 §Decision 3): `grant_entitlement`/`revoke_entitlement` never
read or write `subscription_state`/`subscription_state_changed_at`/
`trial_ends_at`/`seat_limit` — a suspended company's entitlements remain
fully editable, and granting/revoking a module never touches subscription
standing. Verified in tests, not just asserted in prose
(`test_entitlement_change_never_touches_subscription_state`).

**The actual enforcement point is unchanged and untouched**:
`professional_services.deps.require_ps_active` (the ADR-BOS-010 §Decision 2
template every future module's router copies) still reads
`companies.settings.active_modules` the same way it always has — this slice
only adds an audited path to flip that flag, never a second enforcement
mechanism. Proven end-to-end in tests, not just at the storage layer: a
tenant's own request against a professional-services route 404s before any
grant, 200s the moment the vendor grants the module (no re-login — the guard
reads live state), and 404s again the moment the vendor revokes it
(`test_granting_and_revoking_actually_changes_what_the_tenant_can_reach`).

**`errors.provisioning.company_not_found`** is reused for the 404 here
(the exact same fact — no such company — as the company-detail route
already established in phase 2) rather than a differently-named entitlement
key for what is semantically identical.

## 13. Subscription Lifecycle Transitions (phase 4, 27.07.2026, ADR-BOS-012)

### 13.1 One reasoned-change endpoint, not one per state

`POST /companies/{company_id}/subscription/transitions` moves a company
between `trial | active | grace_period | suspended | cancelled`, always with
a mandatory `reason`. One endpoint handles every direction — the console's
"suspend" and "reactivate" buttons are the same call with a different
`new_state`, not two backend paths. This is the same reasoned-change shape
`PSDeadlineChange` established (ADR-BOS-012 §Decision: "reused rather than
invented") — including its one real difference from entitlement management:
**there is no idempotent no-op here.** `identity.service.
set_subscription_state` never checks whether `new_state` equals the current
value; re-asserting the same state (e.g. confirming payment again) still
writes its own audit row, exactly as `change_deadline` never suppresses a
deadline "change" to the same date. A transition is a historical event, not
a boolean flag flip.

`platform_audit_log.reason` — a column that has existed, unused, since
migration 0012 first defined the table — gets its first real writer here.

### 13.2 `SUBSCRIPTION_STATES` is Core-owned, unlike profile/module vocabulary

Unlike RepairFlow's business-profile slugs or module keys (both explicitly
*not* identity's vocabulary to validate — §11.3, §12), the five subscription
states live in `identity.service`/`identity.contracts` as real constants
(`SUBSCRIPTION_STATES`, `MUTATION_ALLOWED_SUBSCRIPTION_STATES`), because
ADR-BOS-012 itself calls the enforcement point "Core-owned" and that
enforcement point (`require_subscription_ok`) has to live in the same
module that already owns `Company`. `platform_admin.service.
transition_subscription` validates a requested `new_state` against
`identity_contracts.SUBSCRIPTION_STATES` before ever touching the row.

### 13.3 `require_subscription_ok` — wired narrowly, on purpose

Built as a Core dependency (`identity.deps.require_subscription_ok`,
sibling to each module's own `require_<module>_active`, ADR-BOS-010), but —
an explicit scope decision made with the PO before implementation — wired
onto **`professional_services`'s own mutating routes only** in this slice,
not retrofitted across `serviceflow.customers`/`.assets`/`.service_orders`/
`.commercial`/`.tasks`/`.attachments`/`.contacts`. That retrofit is real,
mechanical, and larger than anything else in this document's phase list (8+
router files outside Business OS's own module boundaries) — a deliberate
follow-up, not an oversight. Until it lands, subscription suspension is
enforced for Professional Services only; RepairFlow's own mutations are
unaffected by a company's subscription state.

**Applied per-route, never at router level.** `require_ps_active` gates its
whole router — reads included — because an inactive *module* really does
mean "hide everything." `require_subscription_ok` must never do that:
ADR-009's degradation promise ("all data visible, export/backup always
available") means reads stay open in every subscription state, including
`cancelled`. It sits next to `require_csrf` on each of the 8 routes that
already required it — the existing CSRF-required set turned out to be
exactly the mutation set ADR-BOS-012 means, so no separate classification
was needed.

**402 Payment Required**, `errors.subscription.mutations_blocked` — the one
new HTTP status this document introduces; no other endpoint in the
codebase needed it before this exact scenario existed.

### 13.4 Verified independent of entitlement, not just declared so

ADR-BOS-010 §Decision 3 ("entitlement and subscription standing are
independent checks") is proven in tests, not only asserted in this
document: a company with `professional-services` entitled but subscription
`suspended` reads successfully (both guards are read-transparent) and gets
blocked on write with `errors.subscription.mutations_blocked` — never an
entitlement-shaped error, and `transition_subscription` never reads or
writes `active_modules` at all.

