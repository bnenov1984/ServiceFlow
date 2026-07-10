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

Not frozen (deliberately open until the blueprint documents): database schema
details, API surface, UI screen specifications, exact package/tooling versions —
these are produced next and freeze at implementation start.

## Change process after freeze

A change to any frozen item requires: written rationale → impact assessment (which
documents, which ADRs, which C-constraints) → PO approval → same-commit update of the
affected ADR/document (status: Amended, with date and reason). "It seemed easier
during coding" is not a rationale (blueprint Part 1, Development Philosophy).

## Standing reconsideration gates

- **Stage-0 gate (ADR-002):** bundled-PostgreSQL hardening spike must pass before
  any Alembic migration exists; otherwise the SQLite ramp executes.
- **Pilot gate:** aggregate boundary (01 §4) and search ranking (ADR-010) are
  re-examined against real pilot-shop behavior before commercial launch.
