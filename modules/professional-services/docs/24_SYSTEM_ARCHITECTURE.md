# PS-24 — System Architecture

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

No new architecture is invented here — that is the point. The module slots
into the existing modular monolith (ADR-001/ADR-BOS-001) exactly as the
module contract (BOS-06) prescribes, and inherits the platform stack:
FastAPI + SQLAlchemy + Postgres + Alembic backend, React SPA frontend,
web-first SaaS deployment (docs/14).

## 1. Placement

```
backend/src/
├── serviceflow/            # existing vertical + today's Core packages
└── professional_services/  # this module (post BOS-08 Phase-3 rename,
                            # Core lives in business_os.*; see §6)
frontend/src/
└── features/ps/            # module SPA features under the shared shell
modules/professional-services/  # this documentation package (no runtime code)
```

Package-internal layout per [10] §1 (clients, catalog, assignments,
actions, tasks, dossier, communications, billing_light, alerts, activity,
contracts.py). Each package: `models.py`, `service.py`, `router.py`,
`schemas.py` following the ServiceFlow file conventions — **pattern reuse**,
zero code reuse.

## 2. Runtime slices

| Slice | How | Platform precedent |
|---|---|---|
| HTTP API | FastAPI routers under `/api/ps/...`, registered in the composition root (`main.py`) — the one sanctioned co-appearance point ([10] §5.4) | ServiceFlow routers |
| AuthN/AuthZ | Core session deps (`identity.deps`) + `require_ps_role` layered on top ([20] §5) | BOS-16 contract |
| Tenancy | TenantContext + `scoped()` chokepoint + RLS on every `ps_*` table (ADR-016) | mandatory |
| Persistence | SQLAlchemy models owned by this module; Alembic revisions labelled `ps` in the single linear history (BOS-06 migrations rule) | platform rule |
| Files | Core storage port (ADR-007); module stores keys, port stores bytes | attachments precedent, port only |
| Jobs | in-process DB-backed jobs (ADR-006): `ps_morning_evaluation` per tenant (engine + notifications + digests, [13] §7, [19] §3) | platform job pattern |
| Events | shared_kernel bus; module publishes `ps_*` catalogue ([09] §5); module's own activity subscriber writes `ps_activity_events` | ADR-011 pattern |
| i18n | `ps.*` namespace in the bg catalog; backend returns message keys only | ADR-015 |
| Health/export | module hooks per BOS-06 (`health`, `export` section) when Етап-3 platform lands | contract |

## 3. The deadline/alert engine — architecture notes

- Pure-domain core: `alerts/engine.py` — functions over plain dataclasses
  (no ORM imports), the unit-test target ([32] §T-1…T-4).
- Set-based read models: list/dashboard risk computed in SQL (indexed
  date columns, [25] §4) using the *same thresholds*; property tests assert
  SQL ≍ pure-function agreement on generated cases ([32] §T-2) — the
  classic dual-implementation risk, managed by testing not by pretending
  one implementation can serve both row-level UX and 5 000-row lists.
- Job scheduling: one morning run per tenant (Sofia-morning), plus
  on-write recompute of the touched assignment. Idempotent by dedup-key
  design ([19] §3); no cron infra beyond ADR-006 jobs.

## 4. Frontend

- Feature folders under the shared shell; module nav contributed per
  BOS-06 `navigation`. Phase-2 frontend boundary rule holds (lib/
  components/i18n never import from features); feature-to-feature isolation
  (deferred R9) becomes real when this module's frontend lands beside
  ServiceFlow's — this module must not import ServiceFlow feature folders
  (adds the concrete case for finishing R9; noted in [35] roadmap).
- Server is source of truth for risk states and derived totals — the SPA
  renders, never recomputes business rules (one implementation of truth;
  display-only countdown niceties allowed).

## 5. What this module adds to the platform (and what it must not)

Adds: nothing to Core in MVP. It is the platform's **module #3 proof** the
same way CS is #2: consuming Core as-is. Wants that are *recorded but not
built*: per-module notification outbox (future extraction candidate once
commercial/CS also need notifications), polymorphic file anchor (BOS-02
already defers this), global search facade (deferred, module ships its own
sources). Must not: modify ServiceFlow, touch its tables, extend Core
"while we're there" — any Core change goes through the platform docs'
process, separately.

## 6. Dependencies & sequencing (BOS roadmap alignment)

- **This module's commitment triggers BOS-08 Phase 3** (Core package
  rename to `business_os.*`) — same trigger CS's ADR-CS-001 claims; the
  rename should precede *code* (not docs) of either module so neither ever
  imports `serviceflow.identity`. Recorded as the roadmap's precondition in
  [35] §Stage 0.
- Module activation (`company_modules`, BOS-06 minimal form) becomes
  necessary the moment two verticals coexist for real tenants — also
  Stage-0 platform work, minimal form only.
- Nothing here depends on Етап 4 (commercial); [21] keeps money local.
- Construction-supervision integration activates only when both modules
  have code ([29] is Proposed, not scheduled).

## 7. Deployment posture

One artifact, all modules, activation by data (BOS-06 lifecycle). SaaS
per docs/14; no new infrastructure (NFR-PS-16). Local-first compatibility:
preserved in principle (in-process jobs, storage port, no cloud-only
service), **not packaged** (assumption A-3, [36]) — matches the platform's
parked local edition.
