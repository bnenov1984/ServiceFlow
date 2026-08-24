# ServiceFlow

Working name (internal) — kept pending the repository-identity rename
(ADR-BOS-008, deferred). A **web-first, multi-tenant SaaS** BusinessOS
platform: **RepairFlow** is the original, implemented service-management
vertical (customers → assets → service orders → repair workflow → invoices,
for Bulgarian repair businesses, 2–10 people); **Professional Services** is
also implemented; **Construction Supervision** is planned only (no backend
yet). A locally-deployed edition remains a **parked future option**
([ops/local-edition](ops/local-edition/README.md)). Guiding principle: simple
on the surface, robust underneath — and pragmatic everywhere: no enterprise
patterns without a concrete ServiceFlow problem; built to be maintained by a
single developer.

## Status

The 11.07.2026 web-first pivot is recorded in
[14_WEB_FIRST_PIVOT.md](docs/14_WEB_FIRST_PIVOT.md). Current status — stage,
BusinessOS phase, active focus, deployment — is authoritative only in
[docs/13_IMPLEMENTATION_PLAN.md](docs/13_IMPLEMENTATION_PLAN.md) (see its
"Repo-Wide Status" block).

Layout: `backend/` (FastAPI modular monolith) · `frontend/` (React SPA) · `docs/`
(documentation and architecture) · `ops/local-edition/` (parked) · see [CLAUDE.md](CLAUDE.md)
for working rules and commands.

## Documentation

Full map, ADR index (V1 ADR-001…018 + BusinessOS + module series), and area
status (frozen/active/living/planned): [docs/INDEX.md](docs/INDEX.md).

## The non-negotiables (short form)

- Data is never hostage: read-only + export on license expiry (ADR-018).
- A backup that isn't proven restorable doesn't count (05).
- Updates can never destroy a shop (04).
- Issued invoices are immutable; corrections annul + reissue (ADR/01/02).
- The timeline is append-only and trustworthy (BR-5).
- UUIDs + company_id from row one; the backup artifact is the SaaS migration path
  (ADR-012/013, constraints C1–C8).
- Changes to frozen items go through the process in [07](docs/07_ADR_INDEX.md) —
  "seemed easier while coding" is not a rationale.
