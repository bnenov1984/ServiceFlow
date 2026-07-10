# ADR-006 — DB-Backed In-Process Background Jobs

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §D6

## Context
V1 needs background work that must survive restarts: nightly backup +
restore-verification (05), license refresh (ADR-009), update checks (04), HEIC
conversion/thumbnails, "ready too long" reminder tasks, retention/GDPR sweeps,
support-package assembly. Volume: tens of jobs per day per installation.

## Decision
A persistent `jobs` table in the application database + async workers inside the
single application service, with cron-like schedules, at-least-once execution,
idempotent handlers, exponential backoff, and job status surfaced in health.
No broker, no second process.

## Alternatives considered
- **Separate worker service with broker (Celery/Redis-class)** — isolation and scale
  that ~20 jobs/day cannot justify; a third service on a shop PC. Rejected; standard
  choice at SaaS scale (see triggers).
- **No background processing (synchronous only)** — impossible: verified backups and
  license refresh are inherently scheduled; PO made them MVP features. Rejected.
- **OS scheduler (Windows Task Scheduler) invoking scripts** — splits logic across
  artifacts, invisible to health checks, fragile permissions. Rejected.

## Consequences
- **Advantages:** zero extra infrastructure; jobs are transactional with domain data
  where needed; single artifact to operate and update; restart-safe by construction.
- **Disadvantages:** jobs share process resources (CPU during HEIC conversion —
  bounded worker concurrency); long jobs must checkpoint.
- **Risks:** a stuck job starving the queue. Mitigation: per-job timeouts, watchdog,
  health surfacing of queue age.

## Reconsideration triggers
SaaS edition load (many tenants' schedules) justifies a real queue; the `jobs` table
contract is designed so handlers move unchanged behind a queue port.
