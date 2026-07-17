# BOS-07 — Deployment Model

Status: **Phase 0 discovery** · Date: 17.07.2026 · Governing facts: the
11.07.2026 web-first pivot ([docs/14](../14_WEB_FIRST_PIVOT.md), ADR-017) made
**cloud SaaS the primary edition** and parked the local Windows edition
(`ops/local-edition/`, ADR-002/005/009/014). The Phase 0 task brief's local-first
assumptions describe the parked edition — conflict reported in
[01 §1](01_REPOSITORY_ASSESSMENT.md#1-architectural-style).

## 1. Current ServiceFlow deployment (implemented / in plan)

- **Dev:** `docker compose -f docker-compose.dev.yml` PostgreSQL 16 + uvicorn +
  Vite dev server; CI against real PostgreSQL (no mocked DB — docs/12 §2).
- **Етап 3 target (ADR-017):** EU host, Docker, managed PostgreSQL + PITR, S3
  storage, TLS, GitHub Actions CD, staging + production. Multi-tenant by RLS
  (ADR-016), one schema, one database.
- **Storage:** local-FS adapter today; S3 adapter behind the same `StoragePort`
  in Етап 3 (ADR-007 amendment).

## 2. Parked local edition (preserved option, not v1)

Per docs/14: native installer + two services + tray (ADR-005), bundled private
PostgreSQL (ADR-002), offline license tokens (ADR-009), owner-triggered updates
(ADR-014) — all validated to spike level and dormant in
[ops/local-edition/](../../ops/local-edition/). The bridge between editions is
the **ADR-012 versioned artifact**: tenant export from SaaS = import into a
future local install, and vice versa (docs/06 inverted by the pivot).

A revived local edition would be **one company per installation** — i.e. a
single-tenant deployment of the same multi-tenant-capable code (one row in
`companies`), not a separate codebase. RLS still runs; it simply guards one
tenant. This is the same "cardinality change, not redesign" bet that paid off in
the pivot, pointed the other way.

## 3. What Business OS adds — and what it must not

Business OS changes **nothing** about deployment in v1: one artifact, one
database, all modules shipped together, activation as data
([06](06_MODULE_CONTRACT.md)). Specifically rejected: per-module containers,
per-module databases, module-level scaling. Reconsideration trigger is the one
in ADR-001: real scale data showing a hot module.

### Deployment-neutral (must work identically in SaaS and local)

These are the things module code may rely on, and the list is deliberately the
existing port/contract set:

- domain + application logic of every module (the pivot proved this holds);
- tenancy enforcement (TenantContext, `scoped()`, RLS) — identical either way;
- `StoragePort` (FS ↔ S3);
- ADR-012 export artifact (the inter-edition bridge);
- DB-backed in-process jobs (ADR-006) — no broker dependency in either edition;
- i18n mechanism, error envelope, generated API types.

### Deployment-specific (owned by Platform Services, never leaked into modules)

| Concern | SaaS edition | Local edition (parked) |
|---|---|---|
| Access gating | subscriptions + trial (ADR-018) | signed license tokens + grace (ADR-009) — both degrade to the same read-only + export-always mode, which is *product* behavior and stays shared |
| Updates | vendor CD (ADR-017) | owner-triggered updater (ADR-014) |
| Backups | managed DB + PITR; tenant export | shop-side artifact + restore verifier (docs/05) |
| TLS/network | public HTTPS | LAN, localhost install (ADR-004 stance) |
| Tenancy cardinality | many companies | one company |

**Rule (Recommended):** module code must not branch on edition. If a module ever
needs edition-dependent behavior, it consumes a Core-provided capability flag
(e.g. "is read-only mode"), not a deployment identifier. Today zero violations
exist — domain modules contain no deployment awareness (verified: no references
to licensing/updater/backup in domain packages).

## 4. Future cloud specifics that stay in Core

Registration/onboarding, billing webhooks, platform admin console, uptime
monitoring, error tracking (Етап 3 scope, docs/13) — none of it is visible to
vertical modules beyond the read-only-mode flag and the activation set.
