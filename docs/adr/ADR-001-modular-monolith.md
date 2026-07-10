# ADR-001 — Modular Monolith

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §D1

## Context
V1 runs on a single shop-owned Windows PC for 1–20 users; V2 becomes cloud SaaS
sharing the same domain core. Operational simplicity (one thing to install, update,
back up) is the top product risk; long-term maintainability and SaaS extraction paths
must survive.

## Decision
One deployable application with explicit module packages (see 03 §5 module map) and
mechanically enforced import boundaries (import-linter class tooling in CI). No
module is independently deployable in V1, including background work.

## Alternatives considered
- **Layered monolith without module boundaries** — less ceremony now; degrades into
  entangled code that makes SaaS-era extraction and team scaling expensive. Rejected.
- **Service split (core / documents / jobs)** — independent scaling nobody needs at
  this size; multiplies ops burden on a shop PC. Rejected.
- **Microservices** — distributed-system complexity with zero demonstrated
  requirement. Rejected per blueprint Part 6 "do not assume".

## Consequences
- **Advantages:** single artifact for installer/updater/backup; boundaries are cheap
  insurance for extraction; per-module testing; onboarding clarity.
- **Disadvantages:** boundary discipline must be enforced continuously; a monolith
  hides coupling if CI rules lapse.
- **Risks:** "just this once" cross-module imports. Mitigation: CI fails on boundary
  violations; exceptions require an ADR amendment.

## Reconsideration triggers
Real SaaS scale data (thousands of tenants) showing a hot module needing independent
scaling; or a second product sharing modules.
