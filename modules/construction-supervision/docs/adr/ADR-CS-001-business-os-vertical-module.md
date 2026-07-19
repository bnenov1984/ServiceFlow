# ADR-CS-001 — Construction Supervision is a Business OS vertical module

Status: Proposed (PO review) · Date: 18.07.2026

## Context

The initiating task asked for a module in the Business OS repository at
`C:\Projects\BusinessOS`, parallel to ServiceFlow, explicitly not a
standalone application and not nested in the ServiceFlow module. That path
does not exist; the actual Business OS repository is the ServiceFlow repo,
where Business OS exists as documented boundaries + CI enforcement
(BOS-00…16, ADR-BOS-001…004, Phases 0–2.5 implemented) with ServiceFlow as
vertical module #1. BOS-08 Phase 5 anticipates exactly this event — "second
real module" — and defines its rules.

## Decision

1. Construction Supervision is **vertical module #2 of Business OS**, built
   inside the existing Business OS repository and deployment (modular
   monolith, ADR-BOS-001). Not a standalone product, not a fork, not part of
   ServiceFlow.
2. Its documentation lives at `modules/construction-supervision/` in this
   repo. The `C:\Projects\BusinessOS` path from the task is recorded as a
   naming/location aspiration only ([29 Q3](../29_RISKS_AND_OPEN_QUESTIONS.md));
   moving/renaming the repo later is mechanical and out of this ADR's scope.
3. Committing to this module (PO acceptance of this package) **arms the BOS
   roadmap triggers**: Phase 3 (Core package rename) becomes scheduled work
   and precedes any CS code; Phase 5 rules (build-own-or-wait, no reach into
   ServiceFlow) bind every CS PR.
4. Dependency law: `construction_supervision` imports Core contracts only;
   never `serviceflow.*`; Core never imports the module. Enforced by
   import-linter in the module's first code PR.

## Consequences

- ServiceFlow's plan keeps priority; CS phases interleave (BOS-08 governing
  constraint).
- A new top-level `modules/` directory now exists holding module product
  docs; whether future module docs consolidate elsewhere is a Phase-3-time
  layout decision — nothing in this package depends on the answer.
- The Business OS platform proof (BOS-00 §9: second module ships on Core
  without touching ServiceFlow domain modules) becomes this module's
  standing acceptance criterion ([30 AC-8](../30_ACCEPTANCE_CRITERIA.md)).

## Rejected alternatives

- **Standalone repository/application** — violates the task's own
  constraints and forfeits Core (tenancy, identity, RLS) that already works.
- **Building inside ServiceFlow's package** — welds two verticals together;
  the exact failure BOS-00 §1 exists to prevent.
- **Waiting for BOS Phase 3 before even documenting** — documentation is the
  Phase 5 commitment evidence; paper first is the cheap, reversible order.
