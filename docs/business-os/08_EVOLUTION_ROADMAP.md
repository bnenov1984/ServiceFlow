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

## Phase 2 — Additive guard rails (revised per review BOS-11 F4/F5) ✅

Implemented 18.07.2026 — see [14_PHASE_2_IMPLEMENTATION.md](14_PHASE_2_IMPLEMENTATION.md)
for the full record.

- **Objective:** the additive-only items:
  1. frontend boundary rule (R9) — enforced without new tooling;
  2. document the `identity/deps.py` dependency set as "Core contract v1"
     (docstring-level, no new package).
- **Revised during implementation:** the roadmap's original R9 text ("feature
  folders never import each other") was checked against the real codebase
  before enforcing it (same ratchet discipline as Phase 1) and found **false**
  — 9 real cross-feature imports exist (customers/order/orders/shell share
  real components, none of it a mistake). Enforcing the literal wording would
  have meant either breaking the build or writing an allowlist covering most
  of the app — not a guard rail. Implemented instead: the boundary that *does*
  hold today, `lib/`/`components/`/`i18n/`/`generated/` never import from a
  feature folder — the frontend's real analogue to R2. R9-as-originally-
  written (true feature-to-feature isolation) is deferred to Phase 5, when a
  second module's frontend gives it something real to protect.
- **Tooling note:** ESLint is not installed in this frontend at all (no
  config, no devDependency, no lint script/CI step existed before this
  phase). Installing a whole new lint framework for one boundary check was
  judged disproportionate (pragmatism directive, CLAUDE.md rule 1); the check
  is instead a small `vitest` test using Vite's native `import.meta.glob` —
  zero new dependencies, rides the existing `npm test` CI step.
- **Code impact:** `frontend/src/architecture.test.ts` (new) +
  `backend/src/serviceflow/identity/deps.py` (docstring only). No production
  behavior changed.
- **DB impact:** none.
- **Risks:** none realized; both changes verified additive via mutation
  testing (a real violation injected and reverted for the frontend check;
  full backend/frontend suites green before and after).
- **Prerequisites:** Phase 1 ✅.
- **Exit criteria:** met — frontend boundary check enforced via existing
  `npm test`; Core contract v1 documented in `identity/deps.py`; R8 fix
  remains correctly scheduled against its trigger, not this phase.
- **Deferred:** R9-as-originally-conceived (full feature-folder isolation) →
  Phase 5. ESLint itself was not installed — revisit only if a concrete need
  beyond this one check arises.
- **Model:** Sonnet.

## Phase 2.5 — Identity public boundary hardening ✅ (naming note below)

Implemented 18.07.2026 — see
[16_PHASE_3_IDENTITY_BOUNDARY.md](16_PHASE_3_IDENTITY_BOUNDARY.md).

> **Naming conflict, reported per this document's own conflict-resolution
> rule:** the implementation task that produced this work named its
> deliverable doc `16_PHASE_3_IDENTITY_BOUNDARY.md` and called it "Phase 3."
> That is a *different* piece of work from this roadmap's own "Phase 3"
> below (package rename to `business_os.*`), which remains entirely
> untouched and still deferred to its stated trigger. To avoid the roadmap
> having two different "Phase 3"s, this entry is filed here as **Phase 2.5**
> — inserted ahead of the original Phase 3 because Identity, specifically,
> already had concrete non-hypothetical application-level reuse (8 routers)
> justifying earlier boundary enforcement, per
> [02_DOMAIN_CLASSIFICATION.md](02_DOMAIN_CLASSIFICATION.md) §3. The
> document keeps its original filename/number (16, "Phase 3" in its own
> title) since renaming a delivered, referenced document after the fact
> risks worse confusion than one cross-referenced naming footnote.

- **Objective:** turn the documented Identity contract (Phase 2's docstring-
  only "Core contract v1") into a mechanically enforced boundary: external
  modules may import `identity.deps`/`identity.contracts` only, not
  `identity.models`/`.service`/`.security`/`.router` directly.
- **Code impact:** one new file (`identity/contracts.py`), two files edited
  (`identity/deps.py` — internal re-export closure + docstring accuracy;
  `service_orders/router.py` — migrated its one real internal-import
  violation), one new import-linter contract, one new focused test. No
  behavior change — full suite green before and after (98/98).
- **DB impact:** none.
- **Risks:** none realized — exactly one pre-existing violation found and
  migrated (low risk, single call site, covered by an existing PDF-rendering
  test); zero baseline/allowlist needed.
- **Prerequisites:** Phase 1 ✅, Phase 2 ✅, a clean checkpoint verified first.
- **Exit criteria:** met — see BOS-16 §9 for the full checklist against the
  originating task's ten acceptance criteria.
- **Model:** Sonnet (mechanical against a discovered, evidence-backed spec).

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
