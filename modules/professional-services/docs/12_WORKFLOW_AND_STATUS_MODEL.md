# PS-12 — Workflow and Status Model

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Answers the commissioned questions directly: what is a template vs instance
vs status vs stage vs task vs checklist item vs milestone vs next action;
who owns statuses; what transition rules are safe; what happens at terminal
states (the last one normatively in [11](11_ASSIGNMENT_LIFECYCLE.md)/ADR-PS-012).

## 1. Concept separation (the seven words)

| Concept | Is | Is not |
|---|---|---|
| **Workflow template** | org-scoped, named, ordered list of stage definitions; optionally the default of one or more service types | a runtime engine; a BPMN process; versioned document |
| **Workflow instance** | the stage-list **copy** owned by one assignment (created at intake) + the current-stage pointer | a separate entity — the copy *is* the instance (09 §3.6) |
| **Lifecycle state** ("status" in the strict sense) | fixed 4-state machine in code ([11]) | configurable |
| **Stage** | one step of a template/instance; user-visible daily "status" | a lifecycle state; a task |
| **Stage category** | code-owned enum on every stage: `work` / `waiting_client` / `waiting_documents` / `review` / `delivery` | user-invented — orgs pick a category per stage, never define categories |
| **Task / checklist item** | granular work inside one stage-agnostic assignment ([15]) | anything the workflow advances on automatically |
| **Milestone** | not modelled (delivery-category stages + official deadline cover the need) | — |
| **Next action** | the single "what happens next" pointer, orthogonal to stage ([14]) | a stage or task |

Why both lifecycle states *and* stages: one configurable flat list (the
ServiceFlow model) cannot satisfy "orgs configure freely" *and* "invariants
must hold" simultaneously — either users can't rename/remove "Delivered"
(not really configurable) or they can (invariants break). Splitting puts
invariants on the fixed axis and vocabulary on the configurable axis.

## 2. Status ownership (commissioned question)

**Recommendation: both levels, with different owners.**

- **Lifecycle states:** owned globally by module code. Identical for every
  organisation; not editable; translated labels only.
- **Stages:** owned by the **workflow template** (org-scoped). Not a global
  org-wide stage pool: a pool invites collision ("Оглед" means different
  things in two workflows) and makes template deletion/renaming hazardous.
  Cross-template dashboards never group by stage *name* — they group by
  **stage category**, which is code-owned and collision-free. This is what
  keeps the dashboard/Kanban/inactivity rules deterministic across
  arbitrarily customised templates.

## 3. Template rules

- Template: name, active flag, ordered stages (2–20), each stage: name
  (org's words), category, sort. Exactly one `delivery`-category stage
  recommended-not-required (validation warns, doesn't block).
- Editing a template affects **future assignments only** (copies, §5).
- Deactivating hides from pickers; deleting allowed only if never used
  (else deactivate) — mirrors service types.
- **Universal default template** shipped at activation (org-editable copy):
  Нова (work) → Изясняване (waiting_client) → Чакане на документи
  (waiting_documents) → Готова за стартиране (work) → В работа (work) →
  Вътрешна проверка (review) → Чакане на клиента (waiting_client) →
  Корекции (work) → Готова за предаване (delivery).
  Note deliberate differences from the commissioned example list: New/…/
  Cancelled/Completed/Delivered/Invoiced entries of that list are lifecycle
  states or facts (invoiced = money fact, [21]), not stages — collapsing
  them into one list is exactly the ambiguity §1 dismantles.
- Service-specific starter templates (expertise, valuation, acts) ship as
  optional seeds; full stage lists live in [../examples/](../examples/)
  and schema form in [../schemas/workflows/](../schemas/workflows/).

## 4. Stage transition rules

- Allowed moves within an instance: **any stage → any stage** (small-firm
  reality: work is messy; a strict linear matrix would fight users), with
  two soft guards: skipping >1 forward or moving backward prompts for an
  optional note; delivery-category stage prompts the deliver lifecycle
  transition. Hard matrix rejected: configurable per-template matrices are
  workflow-scripting creep ([02] §2.1) with no requesting user.
- Every stage change: activity event (from, to, actor, note); powers
  time-in-stage measures later without new schema.
- Stage changes allowed only in `active`/`delivered` states.
- Kanban drag = the same transition API, same guards ([23] S-2a).

## 5. Instance semantics (copy-on-create)

At assignment creation the chosen template's stages are copied to
`ps_assignment_stages`; `current_stage_id` points into the copy. Template
later edited/deleted → in-flight assignments unaffected (their copy is
theirs). Org wants an in-flight assignment on the new shape → explicit
"смяна на работния процес" action: re-copy, map current stage by pick-list,
activity event records the swap. Rare by design.

## 6. Workflow ↔ next action ↔ checklist relationships

- Stage describes *where* the work is; next action *what happens next*;
  checklist *what must eventually all be done*. None advances another
  automatically in MVP (no "all items done ⇒ next stage" automation — the
  human confirms; the system only *suggests*, e.g. J-4 step 4).
- Suggestions are deterministic nudges, dismissible, never state changes —
  consistent with the no-silent-automation principle (AI or otherwise).
