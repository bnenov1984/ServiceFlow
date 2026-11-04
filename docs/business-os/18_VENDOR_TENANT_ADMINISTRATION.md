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
professional_services only by explicit scope decision), §13.3 updated
28.07.2026 (the deferred platform-wide retrofit landed — `require_
subscription_ok` covered all 38 tenant mutation routes at that point), §14
added 28.07.2026 (Tenant Employee Management + Seat Limits — phases 5 and 7
done together: seat-limit enforcement folded into employee create/
reactivate rather than shipped as its own unconsumed engine; its own two
new mutation routes bring the `require_subscription_ok` count to 41), §15
added 28.07.2026 (RepairFlow Business Profiles — phase 6 done: `asset_types`
company-scoped, migration 0015, seeded via a new `company_provisioned`
domain event rather than a direct Core-to-vertical import; no per-profile
content, no controlled profile-change workflow — both explicit PO
decisions), §16 added 28.07.2026 (Security/Audit Hardening — phase 8 done:
route-graph/dependency-graph completeness tests for audit coverage and
cross-plane isolation, replacing per-feature spot checks; docs/11 §1/§7a
threat model extended for the now-built Vendor Control Plane) · Source: PO
directive accepting the frozen product model
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
5. **Seat limits — Done (28.07.2026), see §14, folded into phase 7** rather
   than shipped separately: a seat-limit engine ahead of the one operation
   that consumes it (employee creation/reactivation) would have been an
   abstraction with no real caller, exactly the anti-pattern this document's
   own §6.3 warns against.
   *Commit:* `feat(business-os): add tenant employee management`.
6. **RepairFlow business profiles — Done (28.07.2026), see §15.** The §6.4
   migration (its own PR as recommended, migration 0015): `asset_types`
   company-scoped, seeded per company via the `company_provisioned` domain
   event, backend field-def resolution switched from global to
   company-scoped. All five profiles seed identical content — no
   per-profile field_defs exist yet (explicit PO decision). Not built: a
   tenant-settings profile selector (the profile stays vendor-assigned,
   read-only to the tenant, per ADR-BOS-011 — no selector was ever meant to
   exist) and the §Decision 7 controlled profile-change workflow (its own
   future domain command, `POST /company/profile-migration`, deliberately
   not `PATCH`).
   *Commit:* `feat(repairflow): add company-scoped business profiles`.
7. **Tenant user management — Done (28.07.2026), see §14.** Owner-only
   create/activate/deactivate/role-change, seat-limit enforcement on
   create/reactivate, last-active-Owner protection, tenant `audit_log`
   entries for every mutation.
   *Commit:* `feat(business-os): add tenant employee management`.
8. **Security/audit hardening — Done (28.07.2026), see §16.** Verified the
   §8 test list is already satisfied incrementally by phases 1–7's own test
   files (checked against the list itself, not assumed); the genuinely new
   work was two route-graph completeness tests (audit coverage, full-route
   isolation) plus the docs/11 §1/§7a threat-model extension for the
   now-built Vendor Control Plane.
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

### 13.3 `require_subscription_ok` — wired narrowly first, then platform-wide (28.07.2026)

Built as a Core dependency (`identity.deps.require_subscription_ok`,
sibling to each module's own `require_<module>_active`, ADR-BOS-010).
Landed in two deliberate steps, an explicit scope decision made with the PO
each time:

1. **First wired onto `professional_services`'s own mutating routes only**
   (this same slice, initial commit) — proves the mechanism end-to-end on
   one real module, independent of entitlement, before touching anything
   wider.
2. **Platform-wide retrofit (follow-up, same day)** — mechanically applied
   to every remaining tenant mutation across `serviceflow.assets`,
   `.attachments`, `.commercial`, `.contacts`, `.customers`,
   `.service_orders`, `.tasks`: 30 routes in 7 files, none of them touching
   business logic — the same one-line addition (`Depends(require_
   subscription_ok)` next to the route's existing `Depends(require_csrf)`)
   repeated mechanically. `business_os.identity`'s own `/auth/logout` and
   `/auth/pin-switch` are the sole deliberate exemptions: session mechanics,
   not the "business mutations" ADR-BOS-012 means to gate — a suspended
   company's users must still be able to log out, and PIN-switch to see the
   read-only degraded app.

**Applied per-route, never at router level.** `require_ps_active` gates its
whole router — reads included — because an inactive *module* really does
mean "hide everything." `require_subscription_ok` must never do that:
ADR-009's degradation promise ("all data visible, export/backup always
available") means reads stay open in every subscription state, including
`cancelled`. It sits next to `require_csrf` on every route that already
required it — the existing CSRF-required set turned out to be exactly the
mutation set ADR-BOS-012 means, in every module, so no separate
classification was ever needed.

**Completeness verified structurally, not by sampling.** A dedicated test
(`test_every_csrf_route_outside_identity_also_requires_subscription_ok`)
walks the assembled app's real dependency graph and asserts every CSRF
route also carries `require_subscription_ok`; a second test asserts the
converse (no read route carries it); a third asserts identity's own auth
routes never do. Together these prove completeness across all 38 gated
routes at once, rather than trusting that a mechanical edit repeated 30
times introduced no gaps — plus representative end-to-end HTTP checks on a
second module (`serviceflow.customers`) confirming the mechanism
generalizes beyond professional_services.

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

## 14. Tenant Employee Management + Seat Limits (phase 7, 28.07.2026)

### 14.1 One combined slice, not two

Seat limits (§9 phase 5) and tenant employee management (§9 phase 7) shipped
together, deliberately not in the sequence originally listed. A seat-limit
*engine* built ahead of the one operation that consumes it — creating or
reactivating an employee — would have been exactly the abstraction-without-
a-real-consumer this document's own §6.3 discipline warns against (the same
reasoning that kept `company_modules` a JSONB set instead of a table until a
second consumer existed). `companies.seat_limit` already existed (migration
0014, ADR-BOS-012); this phase is the first and only code that reads it for
enforcement:

```
Tenant Owner creates/reactivates employee
                    ↓
             count active seats
                    ↓
            compare with seat_limit
                    ↓
              allow or reject
```

No migration. `users` already carries every column needed
(`company_id`, `name`, `email`, `password_hash`, `pin_hash`, `is_owner`,
`is_active`); the existing tenant `audit_log` gains two new action strings
(`employee_created`, `employee_updated`) via the same `_audit()` helper
login/logout/pin-switch/`seed_company` already use — no new table, no new
append-only trigger, no `KNOWN_ACTIONS` frozenset (that guard is
`platform_admin.audit`'s own discipline; tenant `audit_log` never had one,
and this phase doesn't introduce one either — consistent with what was
already there, not a new pattern).

### 14.2 `POST /users` and `PATCH /users/{id}` — Owner-only, seat-bounded

`POST /users` creates a new employee (`is_owner` settable at creation).
`PATCH /users/{id}` activates/deactivates and/or changes role in one call —
a PATCH may touch either field, both, or neither. Both routes require
`require_owner` (docs/02 §12: "Company settings, users... Owner ✔, Worker —")
and `require_subscription_ok` (this phase's mutations are ordinary tenant
mutations, gated the same mechanical way every other one is, per §13.3's
retrofit).

**Seat-limit enforcement is symmetric between create and reactivate.**
Creating a new employee and reactivating (`is_active: false → true`) a
previously-deactivated one are the same seat-consuming event from the
limit's point of view, and both are checked identically:
`company.seat_limit is not None and count_active_seats(...) >= seat_limit`.
A `None` limit (BOS-18 §6.3's own escape hatch — "a deliberate escape hatch
for the vendor's own test/demo companies") skips the check entirely, never
partially — proven with a company that creates five employees in a row with
no limit set, and a second test that hits the limit exactly at capacity.

**Idempotent per field, but always audited.** Setting `is_active`/`is_owner`
to the value they already hold changes nothing (`changed=False` is computed
and included in the audit `detail`, same shape as `platform_admin`'s
entitlement grant/revoke) but still writes a row — a tenant admin action
attempted is worth a record even as a no-op.

### 14.3 The last active Owner can never be removed

Every company must keep at least one active Owner, always — enforced by
counting active owners *excluding the employee being modified*, not just
reading the row's current flag: deactivating the last Owner and demoting
the last Owner to Worker are both blocked by the same check
(`errors.employees.last_owner_protected`), because both are "this specific
employee stops contributing to the active-owner count" from the
invariant's point of view. Deactivating *an* Owner when a second one exists
succeeds normally — the protection is about the company never reaching
zero, not about Owners being unable to step back.

### 14.4 Seat usage becomes visible on both sides

`GET /auth/me` gained `seat_limit`/`seat_usage` fields (riding along next to
the existing `active_modules`) — the Tenant Owner's own view of capacity.

Separately, `CompanyAdminMetadata`/`CompanySummary` (the Vendor Control
Plane's company list/detail, §11.5) gained `seat_usage` — closing a gap
flagged when that dataclass was first written (Company Provisioning
Foundation, §11): ADR-BOS-009 §Vendor data visibility explicitly lists
"seat limit and current seat usage (a count of `users`)" as vendor-visible
metadata, deferred at the time only because nothing yet counted active
employees. `identity.service.count_active_seats` — built for this phase's
own enforcement, called directly by `identity.router`'s `/me` and
internally by `identity.contracts._to_admin_metadata` — is the same
function both sides now read; a test creates an employee through the
tenant API and confirms the count the vendor sees increases by exactly
one.

## 15. RepairFlow Business Profiles (phase 6, 28.07.2026, ADR-BOS-011 §Decision 5)

### 15.1 Three scope decisions, made explicitly before implementation

This slice was the largest and riskiest of the four §6 proposed changes —
a real schema transformation of a table every asset in the product FKs
through. Three genuine product/architecture questions had no answer in the
existing documents; the PO decided each before any code was written:

1. **No per-profile content.** `automotive_repair`/`phone_repair`/
   `electronics_repair`/`appliance_repair` are structural placeholders
   only — identity, not behavior. All five profiles seed byte-identical
   `field_defs` today (proven by a parametrized test comparing every
   profile's seeded content against `generic_repair`'s). The
   `business_profile` column exists specifically so a future migration can
   introduce real per-profile content by branching inside
   `serviceflow.assets.service.seed_default_types`, never by touching the
   schema again.

   **Superseded 03.11.2026** (order-workflow-revamp WP-C, Q18, migration
   0034): that future migration landed — `seed_default_types` now branches
   on `business_profile`, each profile seeding exactly one type per the Q18
   seed map (`serviceflow.assets.service.BUSINESS_PROFILE_ASSET_TYPES`; see
   ADR-BOS-011 §Decision 5's 03.11.2026 amendment for the map itself). The
   parametrized "every profile seeds identical content" test this point
   describes was rewritten to assert the opposite
   (`tests/test_repairflow_business_profiles.py`).
2. **A single clean migration, not §6.4's additive-first recommendation.**
   That recommendation (new table alongside the old, cut over, drop the old
   one in a second migration) is written for a scenario with real
   production tenants whose data must survive a rolling deployment. This
   project has none — Etap 2/3's frontend is unbuilt, so nothing has ever
   been deployed. Migration 0015 transforms `asset_types` directly,
   explicitly documented in its own docstring as a pre-launch-specific
   choice; the additive-first strategy is what a *future* schema change
   touching real customer data should use once the platform is live.
3. **No controlled profile-change workflow in this slice.** ADR-BOS-011
   §Decision 7's compatibility-review-and-vendor-approval process for
   changing an *existing* company's profile is a distinct business
   capability — its own domain command, not an extension of
   `ProvisionCompany` and not a `PATCH` on the company resource. Per the
   PO's own framing: changing a profile is an analysis, a compatibility
   check, a possible migration, an audit, maybe a background job — a
   `POST /company/profile-migration` domain command, when it's built, not
   `PATCH /company/profile`. Nothing in this slice implements it; ADR-BOS-011
   §Decision 7 is unchanged.

### 15.2 The cross-boundary problem, and why domain events solved it

`ProvisionCompany` (`platform_admin.service`) needs asset types seeded at
the moment a company is created — but the seed *content* is owned by
`serviceflow.assets`, and `platform_admin`/`identity` are structurally
forbidden from importing any ServiceFlow module
(`core-not-modules`/`vendor-plane-not-tenant-code`, backend/.importlinter).
The established fix for a lateral cross-boundary need elsewhere in this
codebase is a registered Provider port (`service_orders.contracts.
PaymentSummaryProvider`) — but that pattern doesn't fit here: `identity.
service.seed_company` (the dev/CLI path, used by nearly every test fixture
in this repository) *also* needs to trigger seeding, and a Provider port
would mean two call sites each explicitly invoking a registered callback,
with the registration itself needing to happen before either could run.

Instead, this slice reuses `business_os.shared_kernel.events` — the
synchronous, same-transaction domain-event bus `serviceflow.timeline`
already subscribes to for order-related events, applied for the first time
across the Core/vertical edge instead of within ServiceFlow:

- `identity.service.seed_company` and `platform_admin.service.
  provision_company` each `publish(db, DomainEvent(type="company_provisioned",
  company_id=..., data={"business_profile": ...}))` right before their own
  commit — neither imports `serviceflow.assets` at all;
- `serviceflow.assets.service` subscribes (`@subscribe`-decorated,
  registered as a side effect of the module being imported — already
  transitive via `serviceflow.assets.router`, itself imported by
  `serviceflow/main.py`, mirroring exactly how `serviceflow.timeline`
  registers) and seeds the company's own asset-type copies in the *same*
  transaction the publisher is still inside;
- a failure during seeding propagates back through `publish()` to the
  publisher's own commit, so a broken seed rolls back the whole
  provisioning operation — atomicity is free, not something this design
  had to re-solve.

Proven, not just designed: `test_import_linter_catches_identity_importing_
serviceflow_assets`/`..._platform_admin_importing_serviceflow_assets`
(tests/test_architecture.py) confirm a direct import would still be
caught, and `test_asset_type_seeding_subscriber_is_registered` confirms the
side-effect registration actually happened rather than trusting the import
chain.

**One correctness fix this design required that a Provider port wouldn't
have**: `asset_types` is now RLS-protected (§15.3), but company
provisioning runs as an RLS-*exempt* identity/vendor operation with no
tenant GUC bound yet. The subscriber calls `bind_tenant_scope(db, event.
company_id)` before seeding — without it, the very RLS policy this
migration adds would silently reject its own seeding INSERT.

### 15.3 Schema: `asset_types` company-scoped (migration 0015)

`code` (a bare global primary key) becomes a UUIDv7 `id` primary key +
`company_id` FK + unique `(company_id, code)` — the form docs/business-os/18
§6.4 itself recommended over a compound `(company_id, code)` FK ("to match
the rest of the schema... rather than a composite key, which nothing else
in this codebase uses" — confirmed by grep before implementing: zero
composite FKs exist anywhere). RLS added (`FORCE ROW LEVEL SECURITY`,
the standard tenant policy) — `asset_types` moves from RLS-exempt global
reference data to a normal tenant table. `TimestampMixin` added for
consistency with every other company-scoped reference table
(`PSWorkflowTemplate`, etc.).

`assets.asset_type_code` (a global-code FK) becomes `assets.asset_type_id`
(a UUID FK to the per-company row) internally — but **the wire-level API
contract is completely unchanged**: `AssetIn`/`AssetOut.asset_type_code`
still send/receive the same strings ("phone", "vehicle", ...) as before;
`serviceflow/assets/router.py` resolves between the two at the boundary.
Proof: `tests/test_assets.py`, the pre-existing test file, required zero
changes — every one of its assertions about `asset_type_code` still holds
exactly as written before this migration.

Existing companies (none in any deployed environment — local/test data
only) were backfilled in the migration itself with their own copy of the
four current types, tagged with whatever business profile they already had
assigned, or `generic_repair` for companies predating that field entirely
(`identity.service.seed_company`'s own path).

## 16. Security/Audit Hardening (phase 8, 28.07.2026)

### 16.1 Most of §8's list was already closed, incrementally

Re-read against §8's own list line by line before writing anything new: every
phase (2–7) already shipped its own tests for the vendor mutation it added —
atomicity, idempotency, negative cross-plane tests, RLS/isolation checks,
audit-row assertions — matching the "ratchet discipline" docs/business-os/08
established rather than deferring test debt to a final pass. Three §8 items
are not yet applicable rather than missing: the profile-differentiation and
controlled-migration tests (§8's bullets on rejecting an out-of-profile
field, and on the profile-change workflow) have no code to test yet — all
five business profiles seed identical content and no profile-change
endpoint exists (both explicit PO decisions, §15.1) — so those tests wait for
that workflow, not for this phase.

### 16.2 What was genuinely new: route-graph completeness, not per-endpoint checks

The PO's own framing for this phase: prefer route-graph/dependency-graph
tests, the same shape `test_every_csrf_route_outside_identity_also_requires_
subscription_ok` (§13.3) used for the subscription retrofit, over manual
checks written once per endpoint. Two gaps of exactly that shape were found
and closed, both in `tests/test_architecture.py` and
`tests/test_vendor_security.py` (no DB schema change, no production code
change — test-only, matching the commit shape below):

- **`test_every_vendor_mutation_route_writes_an_audit_record`** /
  **`test_no_vendor_read_route_writes_an_audit_record`**
  (`test_architecture.py`): walks the real assembled route graph
  (`_vendor_routes()`/`_dependant_callables()`, the same helpers §13.3's
  sweep uses) and, for every CSRF-guarded route plus login, verifies by
  inspecting the real endpoint and `platform_admin.service` function objects
  (`co_names`, not source text) that it calls a function which itself calls
  `audit.record` — and the reverse for every read route. Previously, audit
  completeness rested on one hand-written assertion per feature (phases 2–4's
  own test files); a new mutation route that forgot to audit would not have
  failed any existing test. It now does, without anyone having to remember
  to add a new assertion for it.
- **`test_every_vendor_route_touches_no_tenant_table`**
  (`test_vendor_security.py`): extends the pre-existing `test_vendor_request_
  reads_no_tenant_table`, which only ever drove the `/me` endpoint, into a
  full sweep — login, both reads, provisioning, grant, revoke, and a
  subscription transition, each invoked for real and checked against every
  tenant operational table. Building it surfaced one true finding about the
  *test*, not the product: the first draft flagged `POST /companies` for
  writing `users`, which is exactly what provisioning is supposed to do (it
  creates the company's first Owner, ADR-BOS-009 Q2) and what `GET
  /companies`'s `seat_usage` is supposed to read (an explicitly vendor-visible
  *aggregate*, §14.4) — `users`/`sessions` are identity-bootstrap tables, not
  the tenant *operational* data (customers, assets, orders, invoices, ...)
  ADR-BOS-009 actually restricts, and the sweep was corrected to check the
  right set rather than loosening it around the finding.

### 16.3 Why the import-linter contracts made this cheaper than it looks

Both new tests lean on structural guarantees phase 1 already built rather
than re-proving them: `vendor-plane-not-tenant-code` means a query against
any tenant table cannot be *written* inside `platform_admin` at all, so the
route-graph sweep is a confirmation of an already-enforced invariant, not the
only thing standing between a vendor route and a tenant table. The two new
tests are valuable precisely because they check the *live* route graph
FastAPI actually assembles and the *live* function objects it will call,
catching a class of mistake (forgetting to audit, forgetting the boundary)
that a correct import graph alone would not.

### 16.4 docs/11 threat model — extended, not rewritten

docs/11_SECURITY_MODEL.md's own header has flagged §1 and §7 stale since the
web-first pivot, with the full rewrite scheduled for Étап 3. This phase does
not do that rewrite — the rest of the public-facing SaaS surface (credential
stuffing, billing webhooks, etc.) is still unbuilt and stays out of scope.
What phase 8 extends is only the slice that is now real: two rows added to
§1's threat table (vendor credential compromise, cross-tenant access via the
Vendor Control Plane) and a new §7a documenting the Vendor Control Plane's
actual, built threat surface — explicitly disambiguated from §7's "vendor
cloud," which is the parked local edition's license/update infrastructure,
an unrelated concept that happens to share the word "vendor."

### 16.5 Verification

`uv run ruff check .` / `uv run mypy` / `uv run lint-imports` (9 contracts
kept) clean; full suite (against a dedicated `serviceflow_test` database, not
the shared dev one, created fresh for this verification rather than reusing
a developer's local `serviceflow` database) **344 passed**, no skips, no
xfails — the three new tests (two audit-completeness, one full-route
isolation sweep) among them.

