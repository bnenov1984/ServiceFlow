# 07 — ADR Index & Architecture Freeze

Status: **Architecture freeze in effect as of 10.07.2026** (PO approval of 00–06 +
this ADR set) · Date: 10.07.2026

## Accepted ADRs

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

## Business OS ADRs (Phase 1+, layered on the freeze above)

Not part of the 10.07.2026 ADR-001…018 freeze — these are later Business OS
phase decisions (`docs/business-os/`), referenced inline throughout that
subtree but not yet collected into a single index anywhere. Listed here only
as each is found missing; the rest of the `ADR-BOS-*` series is not yet
indexed.

| ADR | Decision | Source |
|---|---|---|
| [ADR-BOS-005](adr/ADR-BOS-005-invoice-numbering-ownership.md) | `document_sequences` (order + invoice numbering) stays owned by `service_orders`; `commercial` calls out via `service_orders.contracts.get_next_invoice_number` | docs/business-os/09 Q2, 05 §1 |

**Pivot amendment 11.07.2026 ([14_WEB_FIRST_PIVOT.md](14_WEB_FIRST_PIVOT.md)):**
web-first SaaS is the primary edition; the local edition is parked (ADR-002/005/
009/014 marked superseded-or-parked; ADR-004/007 amended). Domain, workflow,
schema, API and UI documents are unchanged by the pivot; documents 04/05/06 remain
authoritative for the parked local edition and the artifact format.

## What the freeze covers

Frozen as of this date (changes require the process below):

1. **Domain model** — entities, aggregate boundaries, business rules BR-1…BR-10
   ([01_DOMAIN_MODEL.md](01_DOMAIN_MODEL.md), incl. approved OQ-1…5 defaults).
2. **Workflow** — status set, semantic kinds, transition matrix, role matrix
   ([02_BUSINESS_WORKFLOW.md](02_BUSINESS_WORKFLOW.md), incl. OQ-W1…W4 defaults).
3. **Architecture decisions** — ADR-001…015 above.
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
