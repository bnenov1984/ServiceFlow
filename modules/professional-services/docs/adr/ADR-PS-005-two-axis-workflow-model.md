# ADR-PS-005 — Two-axis workflow: fixed lifecycle states + template-owned stages

Status: **Proposed** · Date: 18.07.2026

## Context

Requirements pull in opposite directions: organisations must configure
their own workflows per service type (court expertise ≠ valuation ≠ acts),
yet invariants (deadline streams, terminal control, permissions) must hold
identically for every org. ServiceFlow's model — one global seeded status
list with a frozen code matrix — satisfies the second and cannot satisfy
the first. One fully-configurable list satisfies the first and destroys
the second.

## Decision

1. **Two axes.** A fixed, code-owned **lifecycle state** machine
   (`active → delivered → completed`, cancel branches, PS-11) carries every
   invariant. Org-configurable **stages** carry the vocabulary of progress.
2. **Stages belong to workflow templates** (org-scoped), not to a global
   org pool — answers the commissioned "status ownership" question as
   *both, split by responsibility*: lifecycle globally in code, stages per
   template.
3. Every stage carries a code-owned **category** (`work`, `waiting_client`,
   `waiting_documents`, `review`, `delivery`) — the deterministic bridge
   that lets dashboards, inactivity rules, and cross-template views work
   over arbitrary custom vocabularies.
4. **Copy-on-create:** assignments receive a copy of the template's stages;
   template edits never mutate in-flight work; an explicit swap action
   re-shapes an assignment when truly needed (PS-12 §5).
5. Stage transitions are free-form with soft guards (note prompts); no
   per-template transition matrices (workflow-scripting creep, refused).

## Consequences

- Dashboards/Kanban/engine group by category, never by stage name —
  custom vocabularies cannot break product behaviour.
- UI must hide the axis split (users see stages + big lifecycle buttons)
  — risk R-1, usability-tested.
- Stage-copy rows per assignment (~10) are accepted storage cost.
- The "one status list" simplicity of ServiceFlow is consciously given up;
  this is the single largest structural divergence between the two
  verticals, and it is domain-driven, not stylistic (PS-27 §2.2).
