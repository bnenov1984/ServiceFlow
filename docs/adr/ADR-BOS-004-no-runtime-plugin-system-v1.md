# ADR-BOS-004 — No Runtime Plugin System in v1

Status: **Proposed (Phase 0 discovery, 17.07.2026) — awaiting PO review; not
part of the frozen ADR set** · Source: docs/business-os/06 (module contract)

## Context

"Business OS supports installable modules" invites the enterprise
interpretation: dynamic discovery, entry points, sandboxing, third-party SDKs,
per-module deployment. Nothing in the product model requires any of that: all
modules are first-party, built by the same maintainer, shipped in one artifact
(ADR-BOS-001), and the only user-visible need is that a company sees the
modules it pays for.

## Decision

v1 has **no runtime plugin system**. Modules are ordinary packages compiled
into the artifact and registered in an explicit, reviewed list in the
composition root. "Installable/activatable" means a per-company activation
flag (data) that gates navigation, routes, and seeding — code is always
present, never loaded dynamically, never third-party. The module manifest
(docs/business-os/06) is a declared contract read from linked-in code, not a
discovery mechanism. Uninstall does not exist in v1; deactivation retains data;
data egress is the ADR-012 tenant export.

## Alternatives considered

- **Python entry-point plugins (importlib.metadata)** — dynamic loading of
  code that is, in practice, always the same first-party code; adds failure
  modes (import order, partial availability) with zero product benefit.
  Rejected.
- **Third-party plugin SDK / marketplace** — a platform business we are not
  in; security surface (arbitrary code in a multi-tenant app) incompatible
  with ADR-016's guarantees. Rejected outright for v1.
- **Per-module deployables** — see ADR-BOS-001. Rejected.

## Consequences

- Adding a module = adding a package + list entry + migrations, reviewed like
  any code. Activation UX is a platform-admin/entitlement flag (Етап 3 console
  can carry it later).
- Inactive modules still run their migrations and ship their code — accepted
  cost: empty tables and dead bytes are free at this scale, and one migration
  state per artifact keeps operations trivial.
- The activation flag's enforcement point (router guard + nav filter) is Core
  code — small, testable, and only built when a second module exists.

## Reconsideration triggers

An actual third-party integration business case approved by the PO; or module
count/tenant-entitlement complexity making the static list unmanageable —
neither is foreseeable from the current product roadmap.
