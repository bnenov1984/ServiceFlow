# PS-15 — Tasks and Checklists

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

The smallest task model that solves the target firm's problem — explicitly
not a project-management platform ([02] §2.3).

## 1. One table, two kinds

`Task`: title, `kind ∈ {task, checklist}`, optional assignee, optional
`due_on`, `done_at`/`done_by` (both set together — INV-7), manual sort,
optional note. Both kinds live in `ps_tasks`, identical mechanics, different
presentation:

- **task** — ad-hoc unit of work someone adds during execution ("Провери
  сервитутите", assignee, due date). Shown as a working list.
- **checklist** — instantiated from a template (or added ad hoc): the
  completeness скелет of the service type ("нот. акт получен", "оглед
  извършен"…). Shown as tickable checklist with progress (done/total).

Separate tables were rejected: the entities are behaviourally identical
(assign, date, tick, audit); the split is presentational. A `kind` column
costs nothing and collapses the API/tests/permissions to one path.

## 2. Checklist templates

`ChecklistTemplate` (org-scoped): name + ordered item titles. A service type
may reference one as default (FR-PS-011); intake instantiates it onto the
assignment (copy, same philosophy as workflow stages — [12] §5: template
edits never mutate in-flight work). Ad-hoc instantiation onto any assignment
is also allowed ("добави чеклист…").

Starter templates ship with the example service types; full item lists live
in [../examples/](../examples/) (valuation and court-expertise lists match
the commissioned examples verbatim).

## 3. Rules

| # | Rule |
|---|---|
| T-1 | Completing sets done_at + done_by (INV-7); unticking within the same day by the same user or manager+ clears both, audit-logged; later corrections manager+ only |
| T-2 | Task due dates feed the person's "моята работа" list and workload view; overdue tasks badge the assignment but do **not** change assignment risk state (official deadline owns that axis) |
| T-3 | Deleting: open tasks soft-delete (manager+ or creator); done tasks never delete (history) |
| T-4 | Tasks never block stage transitions or delivery (a warning lists open items at deliver time; the human decides) |
| T-5 | No dependencies, no subtasks, no milestones, no estimates, no recurring tasks in MVP (F-class; trigger: a real firm's need that ordered checklists demonstrably fail — [34]) |
| T-6 | Tasks are assignment-scoped only; standalone org-level todos are out of scope (that's a todo app; the assignment register is the product) |

## 4. Relationship to neighbours

- **Next action** may point at a task (N-8, [14]); completing either offers
  (never forces) completing the other.
- **Document requirements** are *not* checklist items — they carry document
  states (missing/requested/received/waived) and file links ([17]). Starter
  checklists therefore do *not* duplicate "получен документ X" items where
  the service type defines requirements; the seeds keep the two disjoint
  (a consistency rule checked in [38]).
- **Stages** measure the assignment's macro position; checklist measures
  completeness. The deliver-time warning (T-4) is their only interaction.
