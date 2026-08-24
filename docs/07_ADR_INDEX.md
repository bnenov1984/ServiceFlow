# 07 — ADR Index & Architecture Freeze

Status: **Architecture freeze in effect as of 10.07.2026** (PO approval of 00–06 +
this ADR set) · Date: 10.07.2026

## V1 ADRs (ADR-001…018, frozen)

| ADR | Decision | Source |
|---|---|---|
| [ADR-001](adr/ADR-001-modular-monolith.md) | Modular monolith, enforced module boundaries | 03 §D1 |
| [ADR-002](adr/ADR-002-bundled-postgresql.md) | Bundled private PostgreSQL; **SQLite exit ramp gated on Stage-0 spike** | 03 §D2 |
| [ADR-003](adr/ADR-003-python-fastapi-backend.md) | Python + FastAPI + SQLAlchemy + Alembic + Pydantic | 03 §D3 |
| [ADR-004](adr/ADR-004-react-frontend-pwa-stance.md) | React/TS/Vite/Tailwind/TanStack Query; PWA = manifest + localhost install; LAN HTTPS → V1.5 | 03 §D4 |
| [ADR-005](adr/ADR-005-native-installer-two-services.md) | Native installer: 2 services + tray app; bare-metal restore entry | 03 §D5 |
| [ADR-006](adr/ADR-006-db-backed-inprocess-jobs.md) | DB-backed in-process jobs; no broker | 03 §D6 |
| [ADR-007](adr/ADR-007-storage-port-local-filesystem.md) | Storage port; content-addressed local filesystem | 03 §D7 |
| [ADR-008](adr/ADR-008-session-auth-pin-switching.md) | Server-side sessions + per-user PIN fast-switching | 03 §D8 |
| [ADR-009](adr/ADR-009-license-tokens-grace-degradation.md) | Signed license tokens; 30-day grace; read-only degradation, export always | 03 §D9, Q1, A1 |
| [ADR-010](adr/ADR-010-postgres-search-normalization.md) | PostgreSQL search: normalized shadow columns + pg_trgm | 03 §D10 |
| [ADR-011](adr/ADR-011-inprocess-domain-events-timeline.md) | In-process domain events → transactional timeline | 03 §3 |
| [ADR-012](adr/ADR-012-unified-export-format.md) | One versioned artifact: backup = GDPR export = SaaS migration | 05, 06 |
| [ADR-013](adr/ADR-013-uuids-and-company-id.md) | UUIDv7-class IDs + company_id on every record from day one | 06 §C1/C3 |
| [ADR-014](adr/ADR-014-owner-triggered-updates.md) | Owner-triggered updates; rehearsal, auto-backup, auto-rollback | 04 |
| [ADR-015](adr/ADR-015-i18n-externalization.md) | Full string externalization; Bulgarian-only launch | 03 §3 |
| [ADR-016](adr/ADR-016-tenant-isolation-enforcement.md) | Tenant isolation: server-derived context + chokepoint + RLS | 14 (pivot) |
| [ADR-017](adr/ADR-017-cloud-deployment-cd.md) | Cloud deployment (EU host, Docker, managed PG) + CD; supersedes 002/005/014 for SaaS | 14 (pivot) |
| [ADR-018](adr/ADR-018-subscription-billing.md) | SaaS subscriptions: trial, one monthly plan, provider port, webhook inbox; supersedes 009 | 14 (pivot) |

## BusinessOS ADRs (ADR-BOS-*, active — not part of the V1 freeze)

Later Business OS platform-core decisions (`docs/business-os/`). Layered on
top of the freeze above, governed by that subtree's own PO-review process,
not the V1 change process below.

| ADR | Decision | Status |
|---|---|---|
| [ADR-BOS-001](adr/ADR-BOS-001-modular-monolith.md) | Business OS evolves as a modular monolith | Proposed |
| [ADR-BOS-002](adr/ADR-BOS-002-small-platform-core.md) | Small platform core (minimal shared kernel) | Proposed |
| [ADR-BOS-003](adr/ADR-BOS-003-module-data-ownership.md) | Module data ownership | Proposed |
| [ADR-BOS-004](adr/ADR-BOS-004-no-runtime-plugin-system-v1.md) | No runtime plugin system in v1 | Proposed |
| [ADR-BOS-005](adr/ADR-BOS-005-invoice-numbering-ownership.md) | `document_sequences` (order + invoice numbering) stays owned by `service_orders`; `commercial` calls out via `service_orders.contracts.get_next_invoice_number` | Accepted |
| [ADR-BOS-006](adr/ADR-BOS-006-global-search-platform-capability.md) | Global search is a platform capability; modules only index | Accepted |
| [ADR-BOS-007](adr/ADR-BOS-007-stable-domain-event-naming.md) | Stable, module-namespaced domain event names | Accepted |
| [ADR-BOS-008](adr/ADR-BOS-008-repository-identity-rename-deferred.md) | Repository identity rename, ServiceFlow → BusinessOS | Deferred |
| [ADR-BOS-009](adr/ADR-BOS-009-vendor-control-plane-vs-tenant-workspace.md) | Vendor Control Plane vs Tenant Workspace | Proposed |
| [ADR-BOS-010](adr/ADR-BOS-010-application-entitlement-ownership.md) | Application entitlement ownership | Proposed |
| [ADR-BOS-011](adr/ADR-BOS-011-repairflow-business-profiles.md) | RepairFlow business profiles | Proposed |
| [ADR-BOS-012](adr/ADR-BOS-012-subscription-lifecycle-v1-manual.md) | Subscription/licence lifecycle (V1, manually managed) | Proposed |

**Pivot amendment 11.07.2026 ([14_WEB_FIRST_PIVOT.md](14_WEB_FIRST_PIVOT.md)):**
web-first SaaS is the primary edition; the local edition is parked (ADR-002/005/
009/014 marked superseded-or-parked; ADR-004/007 amended). Domain, workflow,
schema, API and UI documents are unchanged by the pivot; documents 04/05/06 remain
authoritative for the parked local edition and the artifact format.

## Module ADR series

Each vertical module owns and indexes its own ADR series — listed here by
pointer only, not duplicated:

| Module | Series | Index |
|---|---|---|
| Professional Services (implemented) | ADR-PS-001…013 | [modules/professional-services/docs/adr/README.md](../modules/professional-services/docs/adr/README.md) |
| Construction Supervision (planned) | ADR-CS-001…007 | no ADR index — see [modules/construction-supervision/docs/adr/](../modules/construction-supervision/docs/adr/) |

## What the freeze covers

Frozen as of this date (changes require the process below):

1. **Domain model** — entities, aggregate boundaries, business rules BR-1…BR-10
   ([01_DOMAIN_MODEL.md](01_DOMAIN_MODEL.md), incl. approved OQ-1…5 defaults).
2. **Workflow** — status set, semantic kinds, transition matrix, role matrix
   ([02_BUSINESS_WORKFLOW.md](02_BUSINESS_WORKFLOW.md), incl. OQ-W1…W4 defaults).
3. **Architecture decisions** — ADR-001…018 above.
4. **Migration constraints C1–C8** ([06](06_LOCAL_TO_SAAS_MIGRATION.md) §2) — these
   bind all V1 implementation.
5. **Operational designs** — update pipeline (04), backup/verification/restore (05),
   with their acceptance criteria as release gates.

**Amendment 11.07.2026 (PO Етап 1 directive):** the blueprint layer is now also
frozen as v1.0 — Database schema (08), API contracts (09), UI navigation (10).
Together with 01–06 and the ADRs this completes the Etap-1 freeze; changes from
here require the process below ("сериозна причина"). Still open: exact
package/tooling versions and anything the documents explicitly defer to a stage
gate (e.g. accountant review outcomes).

## Change process after freeze

A change to any frozen item requires: written rationale → impact assessment (which
documents, which ADRs, which C-constraints) → PO approval → same-commit update of the
affected ADR/document (status: Amended, with date and reason). "It seemed easier
during coding" is not a rationale (blueprint Part 1, Development Philosophy).

## Standing reconsideration gates

- ~~Stage-0 gate (ADR-002)~~ — **void since the 11.07.2026 pivot** (managed cloud
  PostgreSQL; migration #1 unblocked). Re-arms only if the local edition revives.
- **Pilot gate:** aggregate boundary (01 §4) and search ranking (ADR-010) are
  re-examined against real pilot-shop behavior before commercial launch.
- **Accountant gate** (Етап 4) and **billing-provider verification** (ADR-018)
  unchanged.
