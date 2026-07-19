# CS-14 — Workflow Engine

Status: Draft · Date: 18.07.2026

## 1. Two levels of state, deliberately separated

1. **Document state machine** — per generated document instance:
   `draft → ready → prepared → issued → superseded` (+`registered` for the
   passport). Small, closed, identical mechanics for every type; transition
   only via the single transition endpoint (mirrors ServiceFlow BR-4/BR-2
   discipline), each transition guarded and logged (`cs_transitions`).
2. **Project lifecycle** — phases of the construction itself:
   `подготовка → изкоп/основи → груб строеж → довършителни → изпитания →
   предаване → въвеждане в експлоатация` (+ suspended overlay via обр. 10/11).
   **Derived, not stored as editable state**: the phase is a function of
   which documents are issued (обр. 2 ⇒ started; обр. 14 ⇒ груб строеж
   passed; обр. 15 ⇒ предаване; удостоверение ⇒ въведен). No second source
   of truth to drift.

## 2. Phase gates

A gate = completeness/consistency requirements consumed from the rules
engine at a transition attempt:

| Gate | Guarding | Requires (category-V baseline, registry-configurable) |
|---|---|---|
| Structure gate | issuing `act_14` | all structural `act_12`/`act_7`/`act_8` chains closed; обр. 2/3/5/6 issued; дневник present; no structural blocker findings |
| Handover gate | issuing `act_15` | `act_14` issued; installation test protocols per installed system; ПБ становище; dossier inventory complete; chronology clean |
| Passport gate | issuing `technical_passport` | `act_15` issued; certificates ingested (§IV composable); identifier consistency findings = none |

Gates *consume* findings; they own no logic of their own — one engine, one
explanation surface ([13 §4](13_RULES_ENGINE.md)).

## 3. The pour cycle (instance-family choreography)

From the combined sample (9 iterations): обр. 12 (formwork+rebar) → pour
(дневник entry) → wait ≥ curing days → обр. 8 → обр. 7 (level) → next level.
Modeled as a lightweight **chain template** on the instance family: each
обр. 12 structural instance expects a successor обр. 8 within the rules'
chronology window; the dashboard shows open chains ("плоча кота +2,76:
чака обр. 8 от 15.09"). This is scheduling *information*, not enforcement —
site reality drives the order; the system tracks and warns.

## 4. Suspension overlay

`act_10` issued ⇒ project suspended (date-bounded); `act_11` resumes.
Effects: chronology rules treat the window as invalid for act dates;
dashboards show suspended state; participant changes (builder swap in the
sample) anchor to the boundary documents.

## 5. Why no workflow-engine product (challenged and answered)

The state machines are finite, legally fixed, and shared-shaped across types;
transitions are guarded by rules the module already owns. An external engine
(Camunda/Temporal) would add an infrastructure service, a DSL, and a second
place where "what blocks Act 15" is encoded — violating both the pragmatism
directive and BOS-00 §6 ("no generic workflow engine"). If a future module
needs workflow too, generalization is a BOS Phase 6 extraction question with
two implementations as evidence — not a premature framework here
([24 §5](24_INTEGRATION_WITH_BUSINESS_OS.md)).

## 6. Timeline projection

Every transition, issuance, gate pass/fail, suspension emits a domain event
consumed into `cs_timeline_events` (append-only, ADR-011 projection pattern —
same shape as ServiceFlow's timeline, module-owned table). The timeline *is*
the project history view and the dossier's chronological spine.
