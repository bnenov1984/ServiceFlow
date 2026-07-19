# PS-34 — MVP Definition

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Strict three-way classification (commissioned): **MVP** (first shippable),
**post-MVP** (next; concrete, mostly designed), **future** (named trigger
or never). The FR table ([07]) carries the same M/P/F letters; conflicts
between the two documents are bugs ([38] checks).

## 1. MVP (operational control, complete)

Users/roles (Core + ps roles) · clients + contacts · configurable service
types with defaults + starter seeds · assignments (full field set, typed
details, numbering, org label) · lifecycle + configurable workflows (copy
semantics, categories) · next actions (full model) · deadlines (official/
internal, reasoned changes + history, risk states, thresholds, holiday
badges) · inactivity signals I-1…I-7 · tasks & checklists + templates ·
document requirements + dossier files (upload/categorise/preview/download)
· communication log · activity history · in-app notifications (dedup, ack,
snooze, digest, escalation) · dashboard + table + simple Kanban + calendar
+ workload views · search & filters · money-light (agreed price, entries,
derived totals, payment-overdue) · org settings (label, thresholds,
holidays, visibility toggles) · tenant-export participation (when platform
harness exists) · P0 isolation tests.

**MVP exit = acceptance criteria in [37], journeys J-1/J-2/J-3 end-to-end.**

## 2. Post-MVP (designed or design-ready; build on adoption evidence)

| Item | Note |
|---|---|
| Per-assignment threshold overrides (FR-PS-041b) | schema-ready |
| Duplicate-client hint + merge (FR-PS-005, C-2) | normalization exists (Core) |
| File versioning chains (FR-PS-063) | [17] §3 |
| Recurring reminders (FR-PS-046) | `ps_reminders` table |
| Saved views / "my work" defaults (FR-PS-081) | |
| Service-type extras: duration, default price/assignee (FR-PS-013) | |
| Suggested first next action per service type (N-9 full form) | |
| Email + desktop notification channels (FR-PS-094) | needs Етап-3 outbox |
| CSV import of an existing register (J-9 note) | |
| Commercial-module invoicing integration (FR-PS-103) | blocked on Етап 4 |
| Client merge, workers-see-only-assigned org toggle | |
| CS-project links ([29]) | blocked on both modules' code |

## 3. Future (named triggers; some likely never)

| Item | Trigger |
|---|---|
| Email/calendar/messaging ingestion | ≥3 paying firms ask after using the manual log |
| OCR / AI extraction, summaries, suggested checklists/actions | PO AI budget decision; deterministic MVP proven first ([22 principles]) |
| Working-day threshold arithmetic; statutory-term calculator (FR-PS-014/047) | a firm's contractual/statutory need in writing |
| Task dependencies, milestones, estimates (FR-PS-053) | ordered checklists demonstrably fail a real firm |
| Client portal; mobile native app | product-market fit |
| Recurring assignments (accounting monthly closes) | subscription-shaped firm onboarded |
| Reporting/analytics beyond counts | PO-defined questions counts cannot answer |
| Free-text label packs; second UI language | demand |
| Shared platform extraction (notifications, files pipeline, tasks) | BOS-08 Phase-6 two-implementation comparison |
| Workflow scripting, EAV/custom fields, microservices | never ([02] §2) |

## 4. MVP-boundary rationale (the three cuts that hurt)

1. **No email integration in MVP** — the register's value must survive
   manual entry (if it doesn't, integrations won't save it); integration
   cost is platform-shaped (OAuth, sync, dedup) and would eat the MVP.
2. **No real invoicing** — Етап-4 commercial module owns that future;
   money-light covers P11's visibility need ([21]).
3. **Kanban simple, table primary** — volume personas ([22] §3); a
   polished Kanban with WIP limits etc. is PM-tool creep.

## 5. Descope order under pressure (pre-agreed, so panic doesn't decide)

Calendar view (S-2b) → workload screen (S-9-view; dashboard chips remain)
→ Kanban (S-2a) → checklist *templates* (ad-hoc checklists stay) →
money-light (fields hidden, schema stays). **Never descoped:** next
actions, deadline engine + history, inactivity signals, notifications,
isolation tests — they are the product.
