# BOS-11 — Architecture Review (skeptical pass)

Status: **Review of BOS-00…10 + ADR-BOS-001…004, performed 17.07.2026** ·
Reviewer stance: principal-architect adversarial review against the repository
at commit `6c324ff`. Production code was not modified. Corrections marked
**[applied]** were made to the BOS documents in this pass; everything else is a
recorded finding.

## 1. Findings (ordered by severity)

### F1 — HIGH — The review's own baseline assumption ("current local-first, one-company model") contradicts the repository
- **Affected:** review scope itself; BOS-07, BOS-09 Q1.
- **Evidence:** repository's current model is web-first multi-tenant SaaS:
  [docs/14](../14_WEB_FIRST_PIVOT.md) (PO decision 11.07.2026),
  [docs/07 pivot amendment](../07_ADR_INDEX.md), CLAUDE.md, implemented RLS +
  chokepoint (`shared_kernel/db.py`, migrations 0002+, `tests/test_isolation.py`).
  The local one-company edition is **parked** (`ops/local-edition/`).
- **Assessment:** BOS-07 handles this correctly — deployment-neutral module
  rule, local edition as a single-tenant deployment of the same artifact.
  Nothing in the BOS documents blocks a revived local edition. But the question
  keeps resurfacing in task briefs, which means it is not actually settled in
  the PO's head.
- **Correction:** none to documents. **Q1 in BOS-09 must be answered explicitly
  by the PO at this review** — if the answer is anything other than
  "docs/14 stands", BOS-07 and parts of 00/08 need rework before Phase 1.

### F2 — MEDIUM — Proposed docs invented an event-naming convention that does not exist in code
- **Affected:** BOS-06 (manifest example), BOS-03 §2.4.
- **Evidence:** implemented event types are snake_case strings:
  `part_added`, `labor_added` (`service_orders/lines.py`), `task_created`,
  `task_completed`, `task_reopened` (`tasks/service.py`), `attachment_added`,
  `attachment_deleted` (`attachments/service.py`), `note_or_contact_recorded`
  (`contacts/service.py`). BOS-06's YAML listed `order.created`,
  `order.status_changed`, … — names that exist nowhere in the repository.
- **Why it matters:** a Phase 0 document quietly minting a new convention is
  exactly the "proposed presented as existing" failure the brief warns about;
  left alone it would seed a pointless future rename.
- **Correction [applied]:** BOS-06 example now uses the real implemented names;
  BOS-03 §2.4 references the snake_case catalog explicitly.

### F3 — MEDIUM — Numbering sequences were over-promoted toward Core
- **Affected:** BOS-02 (classification row), BOS-09 Q2, BOS-05 §1.
- **Evidence:** exactly one implementation (`service_orders/models.py::
  DocumentSequence`) with exactly one live consumer (order numbers,
  `service_orders/service.py::next_number`). Invoice use is future (Етап 4);
  other-vertical use is hypothetical.
- **Why it matters:** "A (mechanism)" classification + the "tiny Core numbering
  service" option (c) in Q2 rested on hypothetical products needing document
  numbers — the justification BOS-00 §4 explicitly bans. Core admission
  requires two *real* consumers; today there is one.
- **Correction [applied]:** BOS-02 reclassifies numbering to **D (unproven)**
  with the table-ownership question unchanged (Open, Етап 4); BOS-09 Q2 drops
  the lean toward (c) — a Core numbering service may only be *proposed again*
  when a second module actually issues numbered documents.

### F4 — MEDIUM — Phase 2's event-envelope fix was scheduled as standalone churn against frozen-adjacent code
- **Affected:** BOS-08 Phase 2, BOS-04 R8, BOS-02 (events row).
- **Evidence:** the `DomainEvent.order_id` leak is real
  (`shared_kernel/events.py:20`) and worth fixing (R8). But the fix touches
  every publisher (5 modules) plus the timeline subscriber, in the dispatch
  design frozen via ADR-011, for **zero functional benefit to ServiceFlow
  today** — the only publisher context *is* orders.
- **Why it matters:** a dedicated refactor PR against working frozen-adjacent
  code, justified by platform hygiene alone, is the kind of migration step the
  current maturity does not support.
- **Correction [applied]:** BOS-08 Phase 2 retimes the envelope change to the
  **next natural touch of the events code** — the second subscriber (search or
  notifications, Етап 3 per ADR-011's own plan) or the second publisher context
  (commercial, Етап 4) — whichever comes first, with PO sign-off via the 07
  process. Until then the leak stays documented as the known R8 violation.

### F5 — MEDIUM — i18n key renaming proposed with no consumer
- **Affected:** BOS-08 Phase 2, BOS-02 (localization row).
- **Evidence:** `frontend/src/i18n/bg.ts` keys are already de-facto prefixed
  (`orders.*`, `customers.*`, …); no second catalog consumer exists; the Етап-2
  frontend is mid-build and a catalog-wide rename risks regressions in the
  screens just stabilized (commit `6c324ff` fixed PO-reported UI bugs).
- **Correction [applied]:** formal key namespacing is deferred to module #2
  (Phase 5); Phase 2 keeps only the additive ESLint zone rule (R9).

### F6 — LOW — Data-ownership matrix overstated audit-log writers
- **Affected:** BOS-05 §1 (`audit_log` row).
- **Evidence:** `_audit()` is private to `identity/service.py`; its only
  callers are identity flows (login, logout, PIN switch, seeding). No other
  module appends audit entries today, and no Core contract for it exists.
- **Correction [applied]:** row now states writers = Identity only; a Core
  append contract is *future, if ever needed* — not a description of today.

### F7 — LOW — Terminology collision on the word "Core"
- **Affected:** BOS-10; reading of docs/01.
- **Evidence:** [docs/01 §1](../01_DOMAIN_MODEL.md) labels the Service
  Operations area "(core)" meaning *core domain of ServiceFlow*; Business OS
  uses "Core" for the *platform layer*. Same word, opposite ends of the stack.
- **Correction [applied]:** BOS-10 glossary entry for Core now carries an
  explicit disambiguation against docs/01's usage. docs/01 itself is frozen and
  untouched.

### F8 — LOW — "Core must boot with zero ServiceFlow modules present" stated too early
- **Affected:** BOS-00 §3.
- **Evidence:** no requirement before module #2 exists; as phrased it could be
  read as licensing package surgery now.
- **Correction [applied]:** annotated as a Phase-3+/module-#2 exit criterion,
  explicitly not a near-term obligation.

### F9 — LOW — Q1 was marked blocking for Phase 1, but Phase 1 is deployment-agnostic
- **Affected:** BOS-09 Q1.
- **Evidence:** Phase 1 is an import-linter contract (R3) + a metadata test —
  neither depends on deployment direction.
- **Correction [applied]:** Q1 downgraded to "blocking for BOS-07-dependent
  content and for closing Phase 0 review; **not** blocking Phase 1 mechanics".

### F10 — INFO — Dormant ceremony in the module manifest (accepted, no change)
- **Affected:** BOS-06 (`core_api`, `version`, `permissions` fields).
- **Assessment:** these fields have no consumer until module #2 and could be
  called speculative. They were already marked informational/dormant and cost
  nothing (they are documentation, not code). Recorded as accepted; if the
  manifest is ever implemented, implement only the fields the activation flow
  actually reads.

## 2. The ten review questions, answered

| # | Question | Verdict |
|---|---|---|
| 1 | Core genuinely minimal? | **Yes after F3 correction.** Core = what exists and is neutral (identity, tenancy, primitives, health) + Етап-3 platform scope that ADR-017/018 already froze. Nothing else. |
| 2 | Anything in Core only for hypothetical apps? | Numbering was (F3) — corrected to D. Export envelope rests on ADR-012, an existing *documented decision*, not hypothesis — kept, confidence marked Medium. |
| 3 | ServiceFlow independently understandable/deployable? | **Yes.** Phase 0 moved no code; the BOS layer is paper + (Phase 1) additive lint. ServiceFlow's docs/13 plan is untouched. |
| 4 | Boundaries reflect existing code, not greenfield idealism? | **Yes.** Contexts map 1:1 to existing packages (verified imports: search reads Customer/Asset/ServiceOrder models; dashboard reads ServiceOrder/Task — both kept legal via R6). The one greenfield rule (commercial via contracts) applies only to a module that has no code yet. |
| 5 | Data ownership unambiguous? | **Yes**, with exactly one deliberate Open item (`document_sequences`, decision scheduled Етап 4) and F6 corrected. Every existing table has one writer in code today. |
| 6 | Supports local-first one-company model? | The *repo's* current model is SaaS-first (F1); the BOS design keeps module code edition-blind, so the parked local edition remains a deployment of the same artifact. Nothing forces SaaS into a future local build. |
| 7 | Avoids premature multi-tenancy / microservices / event sourcing / generic workflow / runtime plugins? | **Yes.** Multi-tenancy is not introduced by BOS — it pre-exists (ADR-016, P0-tested). The other four are explicitly rejected (BOS-00 §6, ADR-BOS-001/004; workflow-engine rejection in BOS-05 §3 WorkOrder analysis). |
| 8 | Phase 1 reversible and behavior-preserving? | **Yes.** One import-linter contract that already passes + one read-only pytest + doc links. Revert = delete lines. No runtime path changes. |
| 9 | Existing vs proposed distinguished? | Systematically (status vocabulary, Existing/Emerging/Future markers). One slip found and fixed (F2). |
| 10 | Extraction delayed until reuse demonstrated? | **Yes**, and stronger after F4/F5: every extraction is behind a named trigger (module #2, second subscriber, second consumer), none behind a date. |

## 3. Decisions safe to freeze now (recommend PO acceptance)

1. **ADR-BOS-001** — modular monolith for Business OS (direct extension of
   accepted ADR-001; zero new mechanism).
2. **ADR-BOS-004** — no runtime plugin system in v1 (pure risk removal).
3. **ADR-BOS-003** items 1–4 — one writer per table, matrix maintained same-PR,
   public ids only, justified cross-module transactions (codifies what the code
   already does).
4. **BOS-04 R3** as a CI contract (Core ↛ modules) — passes today; freezing it
   is a ratchet, not a change.
5. The **non-unification rulings** in BOS-05 §3 (Customer≠Contact,
   Company≠Organization, User≠Employee, ServiceOrder≠WorkOrder,
   timeline≠audit_log) — each is the *absence* of speculative work.

## 4. Decisions that must remain open

- **Q1** deployment authority — PO must confirm docs/14 stands (F1).
- **Q2** `document_sequences` ownership — decide inside Етап-4 design; option
  (c) (Core service) only becomes proposable with a second real consumer (F3).
- **Q3** second module choice and timing — business decision.
- **Q4** Core package naming — Phase-3 trigger.
- **Q5** activation granularity — Phase 5.
- **Q6** timeline generalization — Phase 5/6, two implementations required.
- **Q7** frontend modularity beyond lint zones — Phase 5.
- **ADR-BOS-002** (small Core) — recommend acceptance *after* the PO reads the
  BOS-02 classification, since it hard-codes the admission test that will be
  quoted in future reviews.

## 5. Final verdict

**READY WITH DOCUMENT CORRECTIONS** — the corrections (F2–F9) are applied in
this pass, so the document set as it now stands is ready for Phase 1, **gated
on one input**: the PO's explicit answer to Q1 (confirm docs/14 / web-first as
the baseline) and acceptance of the §3 freeze list. No production code was
changed by the review; no implementation was started.
