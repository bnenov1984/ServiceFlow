# ADR-PS-013 — Web-first SaaS target; local-compatible, not local-packaged

Status: **Proposed** · Date: 18.07.2026

## Context

The commission references local deployment/backup capabilities and
"local-first compatibility where required by Business OS". Verified repo
reality: the platform pivoted to **web-first multi-tenant SaaS**
(docs/14, 11.07.2026); the local edition is parked (`ops/local-edition/`),
ADR-002/005/009/014 superseded-or-parked; tenant export (ADR-012) is the
portability mechanism.

## Decision

- The module targets the **SaaS deployment only** for MVP (assumption
  A-3): one artifact, module activation by data, no new infrastructure.
- **Local compatibility is preserved as a property, not a deliverable:**
  the module introduces no cloud-only dependency — in-process jobs
  (ADR-006 pattern), storage port for files, Postgres-only persistence,
  no external services. If the platform revives the local edition, this
  module packages with it unchanged in design.
- Backup/restore for tenants = the platform's ADR-012 export envelope;
  the module ships its section (FR-PS-121) and its restore round-trip
  joins the platform CI harness when that exists.

## Consequences

- No dual-deployment testing burden in MVP; the parked option costs only
  discipline (which the platform already enforces: deployment stays out
  of the domain — BOS-00 §8.5).
- If the PO's local-edition option revives, the gap is packaging work,
  not redesign — the property this ADR exists to protect.
