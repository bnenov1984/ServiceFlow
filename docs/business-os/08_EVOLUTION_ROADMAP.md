# BOS-08 — Evolution Roadmap

Status: **Phase 0 discovery — proposed sequencing, needs PO approval** ·
Date: 17.07.2026

Governing constraints:

- **ServiceFlow's delivery plan (docs/13) has priority.** Business OS phases
  interleave with Етап 2–5; none of them may delay or destabilize a stage.
  Phases 0–2 are deliberately tiny; phases 5+ are gated on business events
  (second module committed), not dates.
- Every phase preserves a working ServiceFlow; Phase 1 is fully reversible and
  behavior-preserving.
- "Model" column: recommended Claude model for executing that phase's work —
  **Fable 5** where boundary/contract judgment dominates, **Sonnet** where the
  work is mechanical against an approved spec.

## Phase 0 — Discovery & documentation (this phase) ✅

Objective: boundaries on paper; conflicts reported; decisions staged for PO.
Code impact: none. DB impact: none. Risks: only stale docs if not maintained.
Exit: PO reviews BOS-00…10 + ADR-BOS-001…004, accepts/vetoes each Recommended
item. Model: Fable 5.

## Phase 1 — Ratchet the existing boundaries (first implementation phase) ✅

Implemented 18.07.2026 — see [12_PHASE_1_IMPLEMENTATION.md](12_PHASE_1_IMPLEMENTATION.md)
for the full record (tool selection, verification, failure-message samples).

- **Objective:** make the rules that already hold today mechanically permanent:
  add import-linter contract R3 (Core ↛ modules — passes today), and a pytest
  module asserting every table's mapper lives in its owning package (R5).
- **Code impact:** `backend/.importlinter` (+1 contract) +
  `backend/tests/test_architecture.py` (new). No production code touched.
  **Reversible by `git revert`; zero behavior change** — confirmed: both
  checks verified to pass on the real repo and to correctly fail when a
  temporary violation was introduced, then reverted byte-identical.
- **DB impact:** none.
- **Risks:** none realized; zero pre-existing violations of either rule found,
  so no baseline/allowlist was needed (ratchet applied directly).
- **Prerequisites:** Phase 0 approved; PO confirmed web-first SaaS as the
  authoritative baseline for this phase (docs/14).
- **Exit criteria:** met — CI runs both checks via the existing `lint-imports`
  and `pytest` steps; contracts documented in [04](04_DEPENDENCY_RULES.md) and
  [12](12_PHASE_1_IMPLEMENTATION.md).
- **Deferred from this phase:** linking BOS docs from CLAUDE.md/README — not
  requested in the Phase 1 scope given and touches a file outside this
  phase's explicit non-goals guard; candidate for a small follow-up, not
  silently done here.
- **Timing:** rode alongside Етап-2 frontend work, as planned.
- **Model:** Sonnet.

## Phase 2 — Additive guard rails (revised per review BOS-11 F4/F5)

- **Objective:** the additive-only items:
  1. frontend ESLint zone rule (R9) — lint config, no key renames;
  2. document the `identity/deps.py` dependency set as "Core contract v1"
     (docstring-level, no new package).
- **Retimed out of Phase 2 (BOS-11 F4):** the `DomainEvent.order_id` →
  neutral-subject-reference fix (R8) is real but rides the **next natural touch
  of the events code** — the second subscriber (search/notifications, Етап 3,
  per ADR-011's own plan) or the second publisher context (commercial, Етап 4),
  whichever comes first — **with PO sign-off via the 07 change process**, not
  as a standalone refactor of working frozen-adjacent code.
- **Dropped from Phase 2 (BOS-11 F5):** formal i18n key namespacing — keys are
  already de-facto prefixed; renaming waits for module #2 (Phase 5).
- **Code impact:** frontend lint config + docstrings only.
- **DB impact:** none.
- **Risks:** negligible (additive lint + comments).
- **Prerequisites:** Phase 1; Етап-2 frontend exit (avoid churn while journeys
  are being stabilized).
- **Exit criteria:** ESLint zones enforced in CI; Core contract v1 documented;
  R8 fix scheduled against its trigger in the backlog.
- **Model:** Sonnet (the R8 fix, when its trigger fires, is Fable 5 — the event
  envelope shape is a long-lived contract).

## Phase 3 — Core gets a name (package isolation) — **Deferred trigger, not a date**

- **Objective:** move identity/platform/shared_kernel under a `business_os` (or
  equivalent) package; `serviceflow.*` becomes the vertical. Pure rename +
  import updates; import-linter contracts flip from "list of module names" to
  "package prefix" form.
- **Trigger:** PO commits to building a second product, OR Етап 3 platform work
  starts colliding with ServiceFlow naming in practice. **Not before** — a
  rename without a second consumer is cost with no proof.
- **Code impact:** large mechanical rename (high-churn, low-risk); alembic
  version table untouched (revisions are strings).
- **DB impact:** none (table names unchanged).
- **Risks:** merge pain with in-flight branches → do between stages;
  git history noise.
- **Prerequisites:** Phases 1–2; clean working tree across the team (one dev —
  cheap).
- **Exit criteria:** CI green; `business_os` imports nothing from
  `serviceflow.*` (contract R3 now structural).
- **Model:** Sonnet (with Fable 5 reviewing the final boundary file).

## Phase 4 — First contract in anger: commercial module (rides Етап 4)

- **Objective:** build invoicing/payments (already planned, docs/13 Етап 4) as
  the first contract-disciplined module: `service_orders/contracts.py` (billable
  lines, buyer snapshot), `commercial/contracts.py` (order balance, invoice
  status), import-linter R4 contracts added the same PR. No extraction — the
  module simply *starts* clean because it starts empty.
- **Code impact:** Етап-4 scope as planned + the contracts files (small).
- **DB impact:** Етап-4 migrations as planned (invoices, invoice_lines,
  payments); resolve the `document_sequences` ownership question (BOS-05 §1)
  in the migration design.
- **Risks:** contract ceremony slowing Етап 4 — mitigation: contracts are plain
  typed functions, not new infrastructure; accountant gate unchanged.
- **Prerequisites:** Етап 3 done (its own plan); Phase 1 contracts in CI.
- **Exit criteria:** commercial imports service_orders *contracts only*
  (lint-enforced); P0-2/P0-3 green.
- **Model:** Fable 5 for contract design; Sonnet acceptable for the CRUD bulk.

## Phase 5 — Second real module (the platform proof)

- **Objective:** build the first non-ServiceFlow vertical (candidate choice is
  an Open decision — BOS-09 §Q3) on Core as it exists. Explicit rule: where the
  new module wants something ServiceFlow has (tasks, attachments, contacts),
  it **builds its own or waits** — extraction happens in Phase 6 from *two*
  concrete implementations, not one.
- **Code impact:** new module package + activation model
  ([06](06_MODULE_CONTRACT.md)) in its minimal form (`company_modules` flag,
  nav gating).
- **DB impact:** new module's own tables; `company_modules`.
- **Risks:** the big one — second product splits solo-dev focus. That is a
  business decision, not an architecture one; architecture just keeps the cost
  of entry low.
- **Prerequisites:** PO product decision; Phase 3 rename done (so module #2
  never imports `serviceflow.*`).
- **Exit criteria:** module #2 in production for at least one real company;
  list of duplicated capabilities written up as extraction candidates.
- **Model:** Fable 5.

## Phase 6+ — Extract proven duplicates, one at a time

Only capabilities that both modules implemented and that diverge in no
essential way get promoted to shared modules (per capability: proposal → PO →
extraction with data migration plan). Expected first candidates based on
[02](02_DOMAIN_CLASSIFICATION.md): document generation plumbing, numbering,
possibly attachments. Each extraction is its own mini-project with the 05
ownership matrix updated in the same PR. Model: Fable 5 per extraction design.

## Explicit non-plan

No phase renames ServiceFlow tables, splits databases, introduces services,
or builds the module registry ahead of module #2. If Business OS never gets a
second module, phases 3+ simply never fire and ServiceFlow has lost nothing —
that property is the acceptance test for this roadmap.
