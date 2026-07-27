# ADR-BOS-009 — Vendor Control Plane vs Tenant Workspace

Status: **Proposed (audit-driven, 26.07.2026) — awaiting PO review; not part of
the frozen ADR set. Vendor data visibility made explicit 26.07.2026 by PO
clarification 2 — see §Vendor data visibility.** · Source:
docs/business-os/18 (audit), ADR-018 §Decision ("platform admin console"),
docs/13 Етап 3 ("Платформена админ конзола")

## Context

The accepted product model (PO directive, 26.07.2026) makes Business OS a
platform sold to customer companies, with vendor-controlled entitlements,
subscriptions and seat limits layered above tenant-controlled administration.
Today **none of this separation exists in code**: the only role is
`User.is_owner: bool`, scoped to exactly one company (`TenantContext`); there
is no vendor identity, no cross-tenant listing endpoint, and no admin console
of any kind. `activate_module()` — the one function that touches entitlements
— is reachable only from `serviceflow/seed.py`, a composition-root CLI script,
never from an HTTP route. ADR-018 already named a future "platform admin
console (vendor)"; this ADR is the first concrete design for it.

## Decision

**Two planes, one deployment.** Business OS Platform splits into a **Vendor
Control Plane** (vendor staff only, spans all companies) and a **Tenant
Workspace** (one company's own administration + its activated apps) — both
ship inside the same modular-monolith artifact (ADR-BOS-001/004); the Vendor
Control Plane is a distinct route namespace and package, never a separate
deployable.

**Three roles:**

| Role | Identity | Scope | Data model |
|---|---|---|---|
| **Vendor Administrator** | Business OS vendor staff | All tenant companies, via the Control Plane only | New Core table, `platform_admins` — **not** a row in `users`, no `company_id` |
| **Tenant Owner** | `User.is_owner = true` | One company | Existing `users` table (unchanged) |
| **Tenant Employee** | `User.is_owner = false` | One company | Existing `users` table (unchanged) — a role label, not a new entity (docs/business-os/10 already rejects a modeled "Employee") |

**Vendor and tenant identities are structurally separate, permanently.**
`platform_admins` is a new Core table: id, name, email, password_hash,
is_active — no `company_id`, RLS-exempt by the same compensating-control
discipline `users`/`companies` already use (centralized queries in one
service). A vendor-admin session is a **distinct session kind** (its own
cookie name or a `kind` discriminator on the existing `sessions` shape) that
can never resolve into a `TenantContext`, and a tenant session can never
resolve into a vendor-admin context. There is no code path where the same
authenticated request can hold both.

**Permitted / prohibited actions:**

| | Vendor Administrator | Tenant Owner | Tenant Employee |
|---|---|---|---|
| Create a company + its first Owner | ✅ | ❌ | ❌ |
| List/browse other companies | ✅ (Control Plane only) | ❌ | ❌ |
| Grant/revoke module entitlements | ✅ | ❌ | ❌ |
| Set subscription state, seat limit | ✅ | ❌ | ❌ |
| Suspend/reactivate a company | ✅ | ❌ | ❌ |
| **Assign** the initial RepairFlow business profile (at provisioning) | ✅ | ❌ | ❌ |
| **Change** the business profile once operational data exists | ✅ (on tenant request, after compatibility review — ADR-BOS-011 §7) | ❌ (may request only) | ❌ |
| Configure *within* the assigned profile (workflow templates, statuses, warranty defaults) | ❌ | ✅ | per future permission |
| Read cross-tenant administrative **metadata** | ✅ (see below) | ❌ | ❌ |
| Read tenant **operational data** (customers, assets, orders, engagements, documents, invoices, notes) | ❌ (aggregate counts only — see below) | ✅ | ✅ (same as Owner today — no finer read-permission exists yet) |
| Manage own company's employees | ❌ | ✅ | ❌ |
| Read own company's audit trail | ❌ (vendor's own `platform_audit_log` is separate) | ✅ | ❌ |

### Vendor data visibility — metadata-first, not tenant-business-data-first

**Governing principle: vendor visibility is metadata-first, not
tenant-business-data-first.** A vendor administrator administers *companies
as customers*, not *companies' businesses*. This makes ADR-018's original
"no browsing of tenant business data beyond counts" concrete on both sides:

**Visible by default** — administrative metadata about the tenancy itself:

- company identity (name, requisites, creation date, id);
- subscription/licence status and dates (ADR-BOS-012);
- activated applications / entitlements (ADR-BOS-010);
- seat limit and current seat usage (a count of `users`, not the user
  list's business content);
- RepairFlow business profile (ADR-BOS-011 — assigned by the vendor, so
  necessarily visible to them);
- suspension status and its reason;
- deployment/version/health metadata where available (ADR-017's
  operational telemetry);
- internal support notes (vendor-authored, vendor-only — never surfaced to
  any tenant role);
- platform audit history for that company (`platform_audit_log`).

**Not visible by default** — tenant operational data, i.e. the business the
customer runs inside the product:

- customers (`customers`);
- assets (`assets`, `asset_identifiers`);
- service orders and everything in the aggregate (diagnoses, part/labor
  lines, accessories, tasks, attachments, timeline);
- PropertyFlow engagements (`ps_clients`, `ps_assignments`,
  `ps_next_actions`, and their stage/deadline history);
- documents (protocols, generated PDFs, uploaded files);
- invoices, payments and any tenant financial transaction (`invoices`,
  `invoice_lines`, `payments`);
- contact records and notes authored by the customer company.

Aggregate counts of the above (e.g. "1 240 orders") are metadata and remain
visible; individual rows and their contents are not. A vendor administrator
never gets an implicit "view as this company" capability from `company_id`
alone.

**Future support access to tenant operational data** — when a real support
case eventually needs it — must be **separately designed, explicitly
authorised (ideally by the tenant), time-bounded where practical, and
strongly audited** (every accessed record logged, not merely the session
grant). It is **out of scope for the V1 Vendor Console**, and it must never
arrive as a side effect of the Control Plane existing or of an
RLS-exemption convenience. Same conclusion for vendor impersonation, which
is one specific implementation of this and is likewise excluded from V1
pending its own security review.

**Tenant isolation requirement, restated for the Control Plane:** every
Control-Plane endpoint that targets one company takes that company's id as an
explicit path parameter, resolved and existence-checked server-side, and every
resulting mutation is audited with that id — never inferred from anything
client-supplied that doubles as authorization (the same "server-derived
context, not client-supplied" discipline ADR-016 already applies to
`TenantContext`, extended to the vendor side).

**Audit logging:** every Vendor Control Plane mutation writes an append-only
record — actor (`platform_admin_id`), target `company_id`, action, reason
(free text, required for suspend/override/limit-change), timestamp. This is a
**new table** (`platform_audit_log`, Core-owned) rather than reusing the
existing tenant `audit_log` (whose `user_id` FK is typed to `users.id`, not
`platform_admins.id` — mixing actor types in one FK column is the kind of
"generic entity replacing a concrete one" the platform's own anti-goals
reject, docs/business-os/00 §7). See docs/business-os/18 §6 for the full
recommended shape — not implemented by this ADR.

**Console deployment shape:** a separate route namespace (backend:
`/api/v1/platform-admin/*`, own `require_platform_admin` FastAPI dependency
that cannot be satisfied by a tenant session; frontend: a separate route tree,
e.g. `/vendor/*`, never linked from `AppShell`'s tenant nav and never
reachable by a tenant-authenticated browser session). Not a separate
application, not a separate deployment, not a subdomain in v1 — consistent
with ADR-BOS-001 (modular monolith) and ADR-BOS-004 (no independently
deployable parts).

## Alternatives considered

- **A single `is_platform_admin` boolean added to the existing `users`
  table** — rejected outright. The task's own constraints forbid merging
  vendor and tenant roles; beyond that, `users` rows are tenant-scoped by
  construction (`company_id` NOT NULL) and reusing the row for a
  cross-tenant identity would either force a nullable `company_id` (weakening
  every existing tenant-scoping assumption) or a synthetic "vendor company"
  (an Organization-above-Company concept explicitly rejected in
  docs/business-os/05 §3).
- **Separate deployment/subdomain for the Vendor Console** — rejected for v1:
  doubles operational surface for a solo maintainer (BOS-09 R-7), and
  route-namespace + separate-session isolation is sufficient given RLS
  already isolates the blast radius at the data layer.
- **Full RBAC for vendor staff (multiple vendor roles/permissions)** —
  rejected for v1: no evidence of more than one vendor admin tier being
  needed yet; `platform_admins.is_active` is the whole permission model,
  matching docs/business-os/02's existing minimal-RBAC-until-proven stance
  for tenant roles.
- **Reuse `audit_log` with a nullable second actor-type column** — rejected;
  see §Decision, a new table is cleaner than a dual-typed FK.
- **Give vendor administrators read access to tenant operational data by
  default "because support will need it"** — rejected. Support demonstrably
  needs *metadata* (is the subscription active, which apps are on, how many
  seats, what did the vendor last change) for the overwhelming majority of
  cases; needing a customer's actual order rows is the rare case, and
  granting it standingly to make the rare case convenient inverts the
  privacy default for every tenant permanently. The rare case gets its own
  designed, authorised, time-bounded, audited path later (§Vendor data
  visibility) — an escape hatch, not the front door.
- **Rely on "vendor admins are trustworthy staff" instead of a technical
  boundary** — rejected: the tenant's customers' personal data (names,
  phones, device passcodes — docs/11 §5) sits behind this line, and the
  product's own GDPR posture (docs/11 §6) treats the tenant as controller.
  A policy is not a control.

## Consequences

- No tenant-facing code changes — `TenantContext`, `identity.deps`, and every
  existing router are untouched by this ADR.
- The Vendor Console cannot be built incrementally by extending `identity`;
  it needs its own small package (`business_os/platform_admin/` or similar)
  with its own models/service/router, following the same internal-boundary
  discipline `identity` already demonstrates (docs/business-os/16).
- `activate_module` and friends move, when the console ships, from
  "CLI-only" to "vendor-console-only, audited" — see ADR-BOS-010.
- A new migration is required before any of this is real (`platform_admins`,
  `platform_audit_log`, a session-kind discriminator) — **not authored by
  this ADR**; see docs/business-os/18 §6 "Recommended data model changes."
- **The metadata/operational-data line has a concrete enforcement
  consequence**: Control-Plane queries read `companies`, the proposed
  vendor tables, and *counts* over tenant tables — they must never
  `SELECT` tenant business rows. Since `platform_admins` sessions produce
  no `TenantContext`, RLS's fail-closed GUC policy already denies those
  reads by default (an unset `app.company_id` yields zero rows, ADR-016);
  the Control Plane must be built so it never needs to bypass that, rather
  than being granted an RLS exemption for convenience. Counts are the one
  sanctioned aggregate read and should go through an explicit, named
  counting function, not ad-hoc queries.
- **Provisioning gains a required input**: the initial RepairFlow business
  profile is assigned by the vendor at company creation (ADR-BOS-011
  §Decision 3), so the create-company action is not complete without it.

## Reconsideration triggers

Vendor staff headcount or support-workflow complexity outgrowing a flat
`is_active` model; a compliance requirement forcing physical separation of
the Control Plane (separate deployment) rather than logical separation
(separate route namespace + session kind).
