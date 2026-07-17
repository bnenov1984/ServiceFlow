# ADR-BOS-003 — Module Data Ownership

Status: **Proposed (Phase 0 discovery, 17.07.2026) — awaiting PO review; not
part of the frozen ADR set** · Source: docs/business-os/05 (ownership matrix),
04 (rules R4–R7)

## Context

In one shared database (ADR-BOS-001), the only thing standing between "modular
monolith" and "monolith" is who may touch which table. Today all 21 tables have
a clear owning package by inspection, exactly one ownership question is open
(`document_sequences` — orders write it now, invoices will in Етап 4), and
cross-module reads exist only inside the ServiceFlow vertical
(search/dashboard), where they are sanctioned by docs/03 §5.

## Decision

1. Every table has **exactly one owning module**, recorded in
   docs/business-os/05; the matrix is updated in the same PR as any migration
   that adds or repurposes a table.
2. Only the owning module INSERTs/UPDATEs/DELETEs its tables. Across bounded-
   context edges, reads go through declared query contracts and writes through
   application services or domain events — never direct table/model access.
   Within one bounded context (e.g. ServiceFlow's Service Operations packages),
   direct model reads remain legal.
3. Modules reference other modules' rows by UUIDv7 `id` only (the public
   identifier, ADR-013). FKs to Core tables (`companies`, `users`) are always
   allowed; FKs across context edges require a note in the ownership matrix.
4. Cross-module transactions require an explicit justification citing an
   ADR/BR. Standing exemplar: order state + timeline event in one transaction
   (ADR-011 — history must not diverge from state).
5. Concept pairs analyzed in 05 §3 are **not unified by name similarity**:
   Customer ≠ Contact, Company ≠ Organization, User ≠ Employee,
   ServiceOrder ≠ WorkOrder, sales invoice ≠ supplier invoice ≠ subscription
   billing, timeline ≠ audit log.

## Alternatives considered

- **Schema-per-module / DB-role-per-module enforcement** — real isolation, but
  operational machinery (grants, search_path, migration users) far beyond a
  solo-maintainer product; RLS already provides the security boundary that
  matters (tenant). Rejected for v1; lint + test enforcement instead.
- **Free-for-all with review discipline only** — that is the current state
  minus the paper; it decays silently. Rejected — the matrix plus a ~20-line
  metadata test is nearly free.

## Consequences

- The ownership matrix becomes a living artifact with a same-PR update rule.
- Етап 4 must resolve `document_sequences` ownership before invoices write it
  (docs/business-os/09 Q2).
- Extraction of any module later starts from a written, tested inventory of
  what it owns.

## Reconsideration triggers

Evidence of the lint/test net failing (a second writer reaching a table
unnoticed), or a compliance requirement demanding physical data separation.
