# ADR-BOS-010 — Application Entitlement Ownership

Status: **Proposed (audit-driven, 26.07.2026) — awaiting PO review; not part of
the frozen ADR set** · Source: docs/business-os/18 (audit), ADR-BOS-004/006
(module contract, activation), ADR-BOS-009 (companion)

## Context

Module activation already exists and already works correctly by omission:
`companies.settings.active_modules` (a JSONB string list), read through
`identity.service.is_module_active`/`active_modules` and written through
`activate_module`. Enforcement is real on both sides — backend:
`professional_services.deps.require_ps_active` 404s the entire router when
inactive (the template every future module copies); frontend: `AppShell`
filters nav/app-switcher entries by `me.active_modules`. The gap is not
enforcement, it's **reachability**: `activate_module` has exactly one caller,
`serviceflow/seed.py`, a CLI script — no HTTP endpoint, vendor or tenant, can
change it today. This ADR fixes the target ownership model before the Vendor
Console (ADR-BOS-009) gives *someone* a button that calls it.

## Decision

1. **Entitlement means "may this company use module X at all."** It is owned
   and mutated **exclusively** by the Vendor Control Plane. The storage shape
   already shipped — a per-company boolean set in `companies.settings` — is
   correct for v1 and is not changed by this ADR (confirms
   docs/business-os/09 §Q5's existing recommendation).
2. **The backend guard is mandatory and is the only real enforcement point.**
   `require_ps_active`'s pattern (a request-scoped dependency that 404s
   before any handler body runs) is the standing template: every future
   module's router gets its own `require_<module>_active`. Frontend nav
   hiding is a UX courtesy, **never** a security boundary — already true
   today, restated here so it is never "simplified away" under the
   assumption that hidden-in-the-UI means inaccessible.
3. **Entitlement and subscription standing are independent checks.** A
   company can be fully entitled to RepairFlow and PropertyFlow while its
   subscription is `suspended` (ADR-BOS-012) — in that state, mutations are
   blocked platform-wide by a *separate* `require_subscription_ok`
   dependency, not by flipping entitlement off. Conversely a vendor can
   revoke one module's entitlement for a company that remains fully paid up
   on everything else. The two flags must never be collapsed into one.
4. **Entitlement is not configuration.** Entitlement = the vendor-controlled
   yes/no per module. Configuration = tenant-controlled data *inside* a
   module the company is entitled to (RepairFlow business profile —
   ADR-BOS-011 — workflow templates, status renames, warranty defaults). A
   Tenant Owner can freely reconfigure anything inside an entitled module and
   can never grant the company a new entitlement. This line is restated
   explicitly because "a config flag doubling as an authorization check" is
   the single most common SaaS access-control bug class.
5. **Until the Vendor Console ships, the CLI/seed path remains the only
   mutator — and that already satisfies the model.** Nobody, vendor or
   tenant, can currently activate a module through the running application;
   there is nothing to lock down (Phase 4 finding: no code change required).
   When the console's first screen lands, it must call `activate_module`
   through a `require_platform_admin`-gated, audited endpoint — never a
   general company-settings `PATCH`.

## Alternatives considered

- **Plan-based bundles** (a pricing tier implies a fixed module set) —
  rejected for v1 per ADR-018 (one plan) and BOS-09 §Q5; the boolean set is
  strictly simpler and a bundle-to-modules mapping can sit on top later
  without a schema change.
- **Per-user licensing** — rejected; nothing in the product charges per
  user (BOS-09 §Q5, restated).
- **A dedicated `company_modules` join table now** — rejected for v1; the
  JSONB set already works and a table buys nothing until per-module
  expiry/trial history is a real requirement (flagged as a future trigger
  below, not built now).
- **Letting a Tenant Owner request activation, vendor approves async** — out
  of scope for v1 (task constraint: no tenant self-service entitlement
  changes of any kind, not even a request queue); revisit only as a
  deliberate future UX decision, not an architecture default.

## Consequences

- Zero code changes required today (§Decision 5) — this ADR is a target-state
  fix, not a current-state bug fix.
- ADR-BOS-009's Vendor Console design must expose entitlement changes as
  their own audited action, distinct from subscription-state changes
  (ADR-BOS-012) even though both live in the same console.
- Every future module's router must ship its own `require_<module>_active`
  guard in the same PR as the router itself — a review checklist item, same
  discipline as the R4/R11 import-boundary contracts.

## Reconsideration triggers

A second pricing plan or per-module trial periods — either needs per-module
*expiry*, not just a boolean, which is the point where the `company_modules`
table (rejected above) becomes worth building.
