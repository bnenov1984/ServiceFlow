# ADR-013 — Globally Unique IDs and company_id from Day One

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §6, 06 §C1/C3

## Context
V1 hosts exactly one company per installation; V2 hosts thousands per database.
Retrofitting tenant scoping and de-colliding integer IDs across thousands of local
databases during migration would be the single most expensive avoidable mistake in
the product's future.

## Decision
Every domain record carries: (1) a **globally unique identifier** (UUIDv7-class —
time-ordered for index locality) as its primary identity, and (2) a **company_id**
foreign key — constant within a local installation, meaningful in SaaS. Human-facing
numbers (order №, invoice №) are separate per-company sequences and are never used
as technical identity. Local V1 does not *enforce* multi-tenancy (one company
exists); it *carries* it.

## Alternatives considered
- **Auto-increment integers, add UUIDs at migration time** — guarantees a painful
  remapping project across every foreign key and every printed/exported reference
  precisely when the company can least afford it. Rejected.
- **company_id added "when SaaS starts"** — touching every table, query and index
  under commercial pressure. Rejected.
- **Natural keys (IMEI, phone…)** — mutable, non-unique in practice. Rejected.

## Consequences
- **Advantages:** SaaS import = insert rows as-is under a new tenant (06 Phase 2);
  no collision handling, no remapping, no reference rewriting; support/diagnostic
  references are unambiguous across the fleet.
- **Disadvantages:** UUIDs are unreadable in debugging (mitigated by human numbers
  everywhere users look) and cost a few bytes per row — irrelevant at our volumes.
- **Risks:** developers "simplifying" a new table with serial IDs. Mitigation:
  code-review rule + CI schema check (DEVELOPMENT_RULES at blueprint stage).

## Reconsideration triggers
None — reversing this later is the exact catastrophe it exists to prevent.
