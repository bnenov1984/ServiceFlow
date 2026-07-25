# BOS-09 — Risks and Open Decisions

Status: **Phase 0 discovery** · Date: 17.07.2026 · Decision owner "PO" = product
owner; "dev" = maintainer. "Deadline" is an event, not a date, wherever possible
— consistent with the trigger-based roadmap.

## 1. Open decisions

### Q1 — Which document is authoritative for deployment direction?
- **Why it matters:** the Phase 0 brief assumed local-first; the repo says
  web-first SaaS with local parked (docs/14). Every BOS document leans on the
  answer.
- **Options:** (a) docs/14 authoritative, local = parked second target of the
  same artifact; (b) revert to local-first (would un-do the pivot).
- **Recommendation:** (a) — it is the existing PO decision, implemented in code
  (RLS everywhere, ADR-016/017/018).
- **Deadline:** at Phase 0 review. **Blocking** for closing the Phase-0 review
  and for BOS-07-dependent content; Phase 1's lint ratchet is deployment-
  agnostic and technically unblocked (review BOS-11 F9). **Owner:** PO.

### Q2 — `document_sequences` ownership (docs/08 files it under commercial; code has it in service_orders)
- **Why it matters:** first table two contexts will write (orders now, invoices
  Етап 4); gaplessness is P0-2.
- **Options:** (a) commercial takes the table over in Етап 4, orders call a
  commercial contract for numbering; (b) service_orders keeps it, commercial
  calls an orders contract; (c) tiny Core numbering service owning the table.
- **Recommendation:** decide inside Етап-4 design when invoice code is real:
  keep the table where it is until then, then assign ownership to whichever
  module the design makes the sole writer — (a) or (b). Option (c) (Core
  numbering service) is only proposable when a second real module issues
  numbered documents (review BOS-11 F3). Do not pre-build.
- **Deadline:** Етап-4 design. **Non-blocking** now. **Owner:** dev proposes,
  PO informed (doc amendment via 07 process).

### Q3 — Which second module, when?
- **Why it matters:** every Deferred item in [02](02_DOMAIN_CLASSIFICATION.md)
  keys off this; it also decides Phase 3 timing.
- **Options:** InvoiceFlow (document-processing pipeline — least overlap with
  ServiceFlow, cleanest platform test), StockFlow (highest synergy with
  ServiceFlow part_lines — but tempts premature integration), CRM / PropertyFlow
  / ProjectFlow / SportFlow.
- **Recommendation:** no architectural preference strong enough to push the
  business choice; note only that StockFlow-first maximizes coupling temptation
  and InvoiceFlow-first maximizes independence proof.
- **Deadline:** whenever the business is ready; architecture keeps the option
  open. **Non-blocking.** **Owner:** PO.

### Q4 — Core package naming (Phase 3)
- **Why it matters:** `serviceflow.identity` as the platform's identity package
  is fine until a second product ships code; then the name lies.
- **Options:** (a) `business_os.*` package inside this repo; (b) keep names,
  document roles only; (c) separate repo/package distribution.
- **Recommendation:** (a) at the Phase-3 trigger; (c) is Rejected for v1
  (single artifact, single CI, solo dev).
- **Deadline:** Phase-3 trigger event. **Non-blocking.** **Owner:** dev, PO
  informed.

### Q5 — Module activation granularity (when module #2 exists)
- **Why it matters:** ADR-018 has one monthly plan; modules imply entitlements.
- **Options:** (a) per-company boolean set (`company_modules`), plan-independent;
  (b) plan-based bundles; (c) per-user licensing.
- **Recommendation:** (a) first — it is the smallest thing the admin console can
  flip; billing integration later. (c) Rejected (nothing in the product model
  charges per user).
- **Deadline:** Phase 5. **Non-blocking.** **Owner:** PO (pricing), dev (model).

### Q6 — Does the timeline pattern ever generalize?
- **Why it matters:** module #2 will want activity history; timeline is
  order-anchored with a frozen event catalog.
- **Options:** (a) each module builds its own timeline table on the shared
  event-bus pattern; (b) generic `activity_events(subject_type, subject_id)`
  Core table.
- **Recommendation:** (a) for module #2; revisit (b) only in Phase 6 with two
  implementations on the table. Consistent with the anti-goal on speculative
  generic entities.
- **Deadline:** Phase 5 design. **Non-blocking.** **Owner:** dev.

### Q7 — Frontend modularity
- **Why it matters:** one SPA, one i18n catalog, no enforced folder boundaries;
  module activation must eventually shape navigation.
- **Options:** (a) keep single SPA, add ESLint zones + key namespacing (Phase
  2), activation-aware nav in Phase 5; (b) split into federated builds.
- **Recommendation:** (a); (b) Rejected for v1 (enterprise pattern, no problem
  it solves at this scale).
- **Deadline:** Phase 2 for lint; Phase 5 for nav. **Non-blocking.** **Owner:** dev.

### Q8 — Timeline subscriber's subject-agnostic filter, post ADR-BOS-007 — **Resolved 23.07.2026**
- **Why it mattered:** `serviceflow.timeline.service._record` (the bus's sole
  subscriber) filtered only on `event.subject_id is not None`, not on event
  `type`. After the ADR-BOS-007 rename made `DomainEvent.subject_id` genuinely
  neutral, any module publishing an event with a non-None `subject_id` that is
  *not* a `service_orders.id` would make this subscriber attempt
  `TimelineEvent(order_id=<that id>)` — a foreign-key violation at commit
  time, since `timeline_events.order_id` is FK'd to `service_orders.id` only.
  Discovered while building Professional Services' stage-transition history
  (two-axis workflow slice, 23.07.2026): its `ps_stage_changed` moment was
  deliberately **not** published through the shared bus specifically to avoid
  this — the history row was written directly by
  `professional_services.assignments.service.change_stage` instead.
- **Resolution — option (a) implemented:** `_record` now gates on
  `KNOWN_EVENT_TYPES`, an explicit, hand-maintained `frozenset[str]` of the 23
  event-type strings ServiceFlow's own producers actually publish today
  (attachments, commercial, contacts, service_orders + lines, tasks), defined
  directly in `serviceflow/timeline/service.py` — no new registry, no
  versioned envelope, no persistent event store (option (b), a
  `subject_kind` discriminator, stays Rejected per the reasoning below).
  Verified with two dedicated tests
  (`backend/tests/test_timeline_subscriber.py`): a non-ServiceFlow event type
  with a `subject_id` is ignored before any DB write is attempted (proven via
  a stub session that raises if `.add()` is ever called — no live database
  needed to prove the safety property); a known ServiceFlow type still
  writes its `TimelineEvent` exactly as before. Full regression: 166/166
  backend tests pass against a real Postgres, 0 skipped, 0 failed.
- **(b) require a `subject_kind`/similar discriminator on every publisher** —
  still Rejected: event-framework expansion with only one concrete consumer
  (BOS-00 §7 anti-goal #1); revisit only if a second subscriber actually
  needs to discriminate by kind rather than by an allowlist it owns.
- **Owner:** dev. **Follow-up:** adding a new ServiceFlow event type means
  adding its string to `KNOWN_EVENT_TYPES` in the same PR — not automatic,
  a plain code review item.

## 2. Principal risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R-1 | **Business OS work distracts from shipping ServiceFlow** — the platform exists only if product #1 succeeds | High | Roadmap phases 1–2 are days, not weeks; phases 3+ are event-gated; this document set requires no code |
| R-2 | **Premature generalization creeps in via review** ("make it generic while we're here") | High | Anti-goals in [00 §7](00_VISION_AND_SCOPE.md#7-anti-goals-over-engineering-tripwires) are review-blockers; Group D list gives reviewers a concrete "not yet" citation |
| R-3 | **Boundary erosion the other way** — commercial (Етап 4) built with direct model imports because contracts feel ceremonial | Medium | Phase-4 lint contracts land in the same PR as the first commercial code; R4 is binary and mechanical |
| R-4 | **shared_kernel becomes a dumping ground** (the classic fate) | Medium | R8 rule + review checklist; the one existing leak (DomainEvent.order_id) gets fixed in Phase 2, keeping the layer visibly clean |
| R-5 | **Docs drift** — BOS docs contradict code within months (already happened to docs/03 §platform scope) | Medium | 05 ownership matrix updated in the same PR as any migration (rule proposed in ADR-BOS-003); everything else references code paths, not copies of code |
| R-6 | **Frozen-doc friction** — Phase-2 event-envelope change brushes against ADR-011's frozen dispatch design | Low | Run the 07 change process explicitly; the change is envelope shape, not dispatch semantics |
| R-7 | **Solo-maintainer bus factor** on a growing platform | Low (unchanged) | Modular monolith + docs are already the mitigation; Business OS adds no new operational surface in v1 |
