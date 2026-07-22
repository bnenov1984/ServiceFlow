# PS-36 — Risks and Open Questions

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Uncertainty ledger. Nothing here is hidden inside other documents; every
assumption is explicit, every open question has a recommended default so
the package stays implementation-ready without pretending to certainty.

## 1. Recorded assumptions (safe defaults taken; PO may overturn)

| ID | Assumption | Basis / risk if wrong |
|---|---|---|
| A-1 | The commissioned path `C:\Projects\BusinessOS` does not exist; the Business OS repository is the current repository root, verified by inspection, and modules live in `modules/`. The outer folder/repo is still named `ServiceFlow` — a known, deliberately deferred mismatch, not an oversight: see [ADR-BOS-008](../../../docs/adr/ADR-BOS-008-repository-identity-rename-deferred.md) (target `BusinessOS`, execution tied to BOS-08 Phase 3, not performed now) | verified by inspection; this package needs no change when the rename executes — it already uses paths relative to the repository root, never the outer folder name |
| A-2 | This module is Business OS vertical **#3** (CS is #2); either commitment triggers BOS-08 Phase 3 | both modules' docs claim the trigger — harmless double-claim, noted in [28] §3.1 |
| A-3 | MVP targets web-first SaaS only; local edition stays parked (docs/14); module remains local-compatible in principle | commission mentioned "local deployment"; repo reality is SaaS. If PO revives local, [24] §7 holds — no cloud-only dependency was introduced |
| A-4 | Single operating timezone Europe/Sofia; org-level timezone is a future setting, schema-neutral | [13] §2.5 |
| A-5 | 1–15 users/tenant, ≤50 000 assignments design ceiling | NFR sizing; beyond that is a different product class |
| A-6 | Bulgarian holiday data can ship as maintained module data (annual update task) | small yearly chore, [33] health-checks it |
| A-7 | CS module README's promised adr/samples/schemas dirs don't exist yet (docs 00–21 only) — integration contracts in [29] are designed against its *docs*, not code | verified; contracts marked Proposed, activation gated on both modules' code |

## 2. Open questions (decision needed; default proposed)

| ID | Question | Recommended default | Decide by |
|---|---|---|---|
| Q-1 | Product brand name: keep descriptive "Professional Services / Професионални услуги" or a *Flow brand (CaseFlow/PraxisFlow)? | ship under descriptive name; branding is marketing, id stays `professional-services` either way (ADR-PS-001) | PO, before first pilot |
| Q-2 | Should `worker` change official deadlines on own assignments? | no (current matrix [20] §3) — deadline discipline is the product's promise; revisit on pilot friction | pilot feedback |
| Q-3 | Default staleness threshold 5 working days — right for all service lines? | yes as org-editable default; pilots calibrate per-org | pilot feedback |
| Q-4 | CS integration contract signatures ([29] §3) | design together with CS at first integration PR; nothing frozen now | both modules in code |
| Q-5 | Should Property/Court become entities (cross-assignment reuse, e.g. yearly revaluations)? | no — typed JSONB until a pilot demonstrates reuse pain ([09] §3.6) | post-pilot |
| Q-6 | Money-light visibility default for workers: off (proposed) or on? | off; small firms are sensitive about prices ([21] §5) | PO |
| Q-7 | Does the module ship its own Kanban in MVP or defer entirely? | ship simple version (descope candidate #3, [34] §5) | build-time pressure |
| Q-8 | Pilot selection: one firm per reference line, or three valuers (fastest feedback loop)? | one per line — the generic model's test is heterogeneity ([09] §4) | PO, Stage 6 |

## 3. Architectural risks (with mitigations)

| ID | Risk | Mitigation |
|---|---|---|
| R-1 | **Two-axis model confuses users** (lifecycle vs stage) | UI never shows "lifecycle state" as a concept — users see stages + a few big buttons (Предай, Приключи); the axis split is architectural, not visual. Usability-tested in Stage 5 |
| R-2 | **Dual risk computation drifts** (pure engine vs SQL read models) | property tests T-2; thresholds sourced from one config object |
| R-3 | **Notification fatigue kills trust** | digest collapse + dedup by design ([19] §4); pilot metric: ack rate |
| R-4 | **Registration burden rejected by 3-person firms** (the product's existential risk) | ⚡ budgets in journeys; row actions; combined log+next-action flows; pilot metric: entries/user/day sustained after week 2 |
| R-5 | **Copy-on-create template semantics surprise orgs** ("I edited the workflow, nothing changed") | S-8 banner ([23] §9); explicit swap action |
| R-6 | **Scope gravity toward PM suite / accounting** | [02] anti-goals + [34] §5 descope order pre-agreed; PR review blocks |
| R-7 | **Platform prerequisite slip** (Phase-3 rename, activation) stalls Stage 1 | Stage 0 is tiny and mechanical; if blocked, Stages 1–4 can build against current package names behind a to-rename shim — ugly, reversible, recorded here as the fallback |
| R-8 | **Solo-dev focus split** across ServiceFlow Етапи and this module | BOS-08's own governing constraint; roadmap pauses this module on collision ([35]) — a business call, honestly stated |
| R-9 | **GDPR posture gap at platform level** (DPA, processors) surfaces during pilot sales | flagged to Етап-3 ([28] §3.4); module-side minimisation already maximal |
| R-10 | **Under-modelling risk:** refusing dependencies/milestones/portals could lose deals | triggers named in [34] §3 — the refusals are revisitable, not dogma |

## 4. Failure modes of the product thesis (honesty section)

- If firms won't type, no register wins — R-4 is the one to watch; the
  MVP's fate hangs on quick-entry, not on the engine.
- If every vertical demands deep specialisation (court formats, bank
  templates), the generic assignment thins out — the typed-details +
  configurable-workflow design is the hedge, and [09] §4's three-line test
  is the canary: the day an example stops fitting, revisit before building
  vertical forks.
