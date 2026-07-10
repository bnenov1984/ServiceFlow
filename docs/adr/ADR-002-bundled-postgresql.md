# ADR-002 — Bundled PostgreSQL with SQLite Exit Ramp

Status: **Accepted (architecture freeze), with explicit exit ramp** · Date: 10.07.2026 · Source: 03 §D2

## Context
The database must run invisibly on a non-technical shop's Windows PC, and the same
domain code must later run multi-tenant in the cloud. Data volumes are small
(~15 k orders/year); photos live on the filesystem (ADR-007). Requirements pulling in
opposite directions: zero-admin local operation (favors SQLite) vs. engine parity
with SaaS, JSONB, pg_trgm search, and concurrency-safe gapless numbering (favor
PostgreSQL).

## Decision
Bundle PostgreSQL as a private, installer-managed Windows service: own port, own data
directory, silent install, auto-restart, unattended minor upgrades, no interaction
with any other PostgreSQL on the machine. The application is the only client.

## Alternatives considered
- **SQLite (WAL)** — genuinely strong here: zero-admin, file-copy backups, adequate
  concurrency behind one app process. Rejected *narrowly*: engine divergence from
  SaaS means dual-dialect testing forever or a migration cliff; weaker fuzzy search
  and JSON ergonomics. Kept as the exit ramp.
- **SQL Server Express** — 10 GB cap, licensing friction, no SaaS parity. Rejected.

## Consequences
- **Advantages:** one engine, one migration chain, one set of query semantics from
  local V1 through SaaS; pg_dump/pg_restore powers the verified-backup design (05);
  advisory locks/serializable isolation give gapless invoice numbers cleanly.
- **Disadvantages:** we own PostgreSQL's operational invisibility — service babysitting,
  crash recovery, upgrade automation are our engineering.
- **Risks:** shop-PC hostility (sleep, antivirus, power loss) corrupting confidence.
  Mitigation: Stage-0 hardening spike is a gate (see trigger), health checks, AV
  exclusions applied by installer.

## Reconsideration triggers (binding)
**Stage-0 gate:** if the installer spike cannot demonstrate — silent install,
survival of hard power-off, unattended minor upgrade, restore drill — on reference
hardware, switch to SQLite **before any Alembic migration exists**. After first
customer data exists, the ramp closes and this ADR may only be revisited for SaaS.
