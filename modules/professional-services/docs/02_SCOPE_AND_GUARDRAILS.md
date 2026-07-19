# PS-02 — Scope and Guardrails

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

The pragmatism directive (repo CLAUDE.md rule 1) governs: no enterprise
patterns without a concrete problem of a 1–15-person firm, buildable and
maintainable by a single developer. This document is the standing "no" list;
violating it is a review blocker once implementation starts.

## 1. In scope (the product)

- Assignment register: clients, service types, assignments with owner,
  team, priority, stages, lifecycle states.
- Next-action discipline: one open next action per active assignment;
  surfacing of assignments without one.
- Deadline engine: official vs internal deadlines, task/next-action dates,
  appointments, deterministic risk states, deadline-change history.
- Inactivity/stagnation detection (deterministic signals).
- Tasks & checklists (flat, small), document requirements, file dossier,
  manual communication log, append-only activity history.
- In-app notifications with dedup, acknowledge, snooze.
- Operational dashboard, filterable assignment table, simple Kanban,
  deadline/calendar view, team workload view.
- Minimal money tracking on the assignment (agreed / invoiced / paid /
  outstanding as entries + derived totals) — see
  [21_FINANCIAL_BOUNDARIES.md](21_FINANCIAL_BOUNDARIES.md).
- Organisation settings: service types, workflow templates, warning
  thresholds, labels (visible name of "Assignment").

## 2. Out of scope — permanently (anti-goals)

Appearing in a PR ⇒ review blocker:

1. **Generic workflow scripting** — stages and transitions are data, but
   behaviour is code. No user-defined automation language, no BPMN.
2. **EAV / custom-fields platform** — typed JSONB per module is the standing
   Business OS pattern (docs/08 §4); a "custom fields designer" is rejected.
3. **Enterprise capacity planning** — no Gantt, no resource levelling, no
   utilisation targets, no timesheet policing. Workload = counts and due
   dates only (see [07_FUNCTIONAL_REQUIREMENTS.md](07_FUNCTIONAL_REQUIREMENTS.md)
   §Workload and screen 9 in [23_SCREEN_SPECIFICATIONS.md](23_SCREEN_SPECIFICATIONS.md)).
4. **Document generation engine** — that is Construction Documentation's
   context (and, for invoices, the future commercial module). This module
   stores and organises files; it does not render domain documents.
5. **Accounting** — no ledgers, no VAT logic, no fiscal devices. Money on an
   assignment is operational visibility, not bookkeeping.
6. **Client portal / external users** — v1 users are firm employees only.
7. **Microservices, event sourcing, module-private databases** — modular
   monolith per ADR-001/ADR-BOS-001.
8. **AI in the core loop** — no AI-required feature; AI never writes a
   deadline, status, or next action ([22 architecture principles], ADR-PS-002).
9. **A second tenancy or permission framework** — Core identity/tenancy only;
   module roles stay a flat enum ([20_ROLES_AND_PERMISSIONS.md](20_ROLES_AND_PERMISSIONS.md)).
10. **Speculative shared abstractions** — nothing in this module is built "so
    ServiceFlow can use it too". Extraction only per BOS-08 Phase 6 (two
    proven implementations).

## 3. Out of scope — MVP (deferred with named triggers)

Full classification in [34_MVP_DEFINITION.md](34_MVP_DEFINITION.md). Headlines:

| Deferred capability | Trigger to revisit |
|---|---|
| Email/calendar/messaging integration | ≥3 paying firms ask; manual log proven insufficient |
| Email/desktop notification channels | in-app channel proven used; Етап-3 outbox exists |
| OCR / AI document extraction & summaries | dossier feature adopted; AI budget decision by PO |
| Recurring assignments | a real subscription-shaped firm (e.g. accounting monthly closes) onboarded |
| Task dependencies, milestones as entities | concrete firm demonstrates need beyond ordered checklist |
| Working-day deadline arithmetic | a firm contractually needs statutory working-day terms |
| Per-assignment permission restrictions | a firm >5 people asks for confidentiality walls |
| Invoicing integration | commercial module (Етап 4) ships its contract |
| Client portal, mobile native app | post-product-market-fit |
| Reporting/analytics beyond dashboard counts | PO-defined questions that counts cannot answer |

## 4. Platform guardrails (inherited, non-negotiable)

- Tenant isolation per ADR-016: session-derived tenant context, scoped
  chokepoint, RLS with FORCE on every `ps_*` table; isolation tests are P0.
- Every table: UUIDv7 `id` + `company_id` (ADR-013).
- No user-facing literals; `ps.*` message keys, Bulgarian catalog (ADR-015).
- Module boundary: never import `serviceflow.*` domain modules or platform
  internals; Core via `identity.deps`/`identity.contracts` and
  `shared_kernel` only (BOS-04, BOS-16; import-linter enforced when code
  lands).
- Money is `numeric`; totals always derived (BR-3 discipline).
- No PII in logs (docs/11 §3); data minimisation per
  [30_SECURITY_PRIVACY_AND_AUDIT.md](30_SECURITY_PRIVACY_AND_AUDIT.md).

## 5. Scope tripwires (how we notice drift)

- A screen needs a training session to explain → UX scope violation.
- A configuration option exists that no onboarded firm asked for → remove.
- A table exists without an owning read/write path in this module → boundary
  violation.
- The deadline engine gains a rule that cannot be unit-tested with a frozen
  clock → determinism violation.
- Any feature description contains "engine" for the third time → suspicion of
  §2.1/§2.4 violation; PO review required.
