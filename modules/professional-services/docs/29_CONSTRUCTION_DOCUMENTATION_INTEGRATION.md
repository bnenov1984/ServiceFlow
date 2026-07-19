# PS-29 — Construction Documentation Integration

Status: **Proposed — activates only when both modules have code** ·
Date: 18.07.2026 · Module: `professional-services` · Counterpart:
`construction-supervision` (Phase-0 docs only, docs 00–21 as of this audit)

## 1. Division of responsibility (commissioned split, made binding)

| Concern | Professional Services (this module) | Construction Documentation (CS) |
|---|---|---|
| Client engagement, commercial terms | **owns** | never |
| Assignment, deadlines, owner, priority | **owns** | never |
| Workflow progress, next actions, communication | **owns** | never |
| Delivery to the client, close-out, money | **owns** | never |
| Structured construction data (project knowledge base) | never | **owns** |
| Act/passport rules, templates, generation, validation, provenance | never | **owns** |
| Generated documents (bytes + immutability rules) | shows via contract | **owns** |

One firm (a supervision company) may run both: PS answers "как върви
поръчката на инвеститора X", CS answers "какво пише в акт обр. 14". Neither
question belongs in the other module. **The contexts stay separate**
([10] §2 Partnership) — merging them is explicitly refused.

## 2. The link

`ps_assignment_links` row with `relation = cs_project`, `target_module =
'construction-supervision'`, `target_ref = ⟨CS project id⟩` ([25] §1).
Properties:

- **Opaque reference, no FK** across module tables (BOS-04/05 discipline);
  dangling links render as "недостъпен проект" — tolerated, surfaced.
- Created from either side: PS S-4 "Свържи със строителен проект" (picker
  via CS contract) or CS project screen "Свържи с поръчка". Both write the
  same PS-owned link row through PS's contract; CS stores no duplicate
  link (single source of truth — the link is engagement metadata, and
  engagements are PS's domain). CS-side navigation reads it via PS's
  contract.
- Cardinality: an assignment links to ≤1 CS project; a CS project may be
  linked from several assignments over time (yearly acts batches as
  follow-up assignments) — matches [11] §3 follow-up semantics.

## 3. Contracts (typed application interfaces, per ADR-BOS-003)

Both are **Proposed**; they get real signatures in the first integration PR,
designed together with the CS maintainers of that day.

- **CS → PS consumption (PS calls):**
  `cs.contracts.list_projects(company) → [{id, name, site, status}]`
  (picker) · `cs.contracts.project_summary(id) → {name, status,
  deliverables: [{kind, title, issued_at, ref}]}` (S-4 Връзки panel,
  read-only) · `cs.contracts.fetch_deliverable(ref) → bytes/url`
  (view/download; **no copying into the PS dossier** — [17] §4).
- **PS → CS consumption (CS calls):**
  `ps.contracts.assignment_ref(id) → {number, title, client_name,
  official_deadline_on, lifecycle_state}` (CS shows "този проект се води
  по поръчка АС-2026-0137") · `ps.contracts.links_for(company,
  target_module, target_ref) → [assignment refs]`.
- **Events (optional niceties, not dependencies):** PS may subscribe to a
  future `cs_deliverable_issued` to log an activity entry on linked
  assignments ("издаден акт обр. 15") — informational only; PS state never
  changes automatically from CS events (no-silent-automation rule).

## 4. Deliberate non-integrations

- No shared "project" entity, no shared client table (CS models
  participants its own way per its docs), no shared files, no shared
  deadlines. CS deadlines (act dates) are construction facts; PS deadlines
  are engagement promises — the same real-world date may legitimately
  appear in both, entered by humans who mean each.
- PS does not create CS projects, and vice versa. A "създай проект от
  поръчката" convenience button is conceivable later — it would still call
  the CS creation contract explicitly, and is out of scope until both
  modules run in production (F-class).

## 5. Sequencing

MVP ships with the Връзки panel hidden unless CS is active for the company
(module-activation flag, BOS-06 `optional`). Nothing in the PS MVP depends
on CS existing; nothing here blocks CS. The first integration PR requires:
both modules' code exists, activation flags exist, and both contracts are
reviewed together — tracked as open question Q-4 in [36].
