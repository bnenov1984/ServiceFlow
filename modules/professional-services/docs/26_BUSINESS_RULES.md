# PS-26 — Business Rules and Invariants

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Normative rule set. Every rule is unit-testable ([32] maps them);
implementation may not ship a rule below without its test. BR = behavioural
rule, INV = invariant (must never be observable as violated).

## 1. Invariants

| ID | Invariant | Enforcement |
|---|---|---|
| INV-1 | Every `ps_*` row belongs to exactly one organisation; no cross-tenant read/write is possible | company_id NOT NULL + FORCE RLS + scoped chokepoint (ADR-016); P0 isolation tests |
| INV-2 | An assignment always has: client, service type, title, number; number unique per (org, year) | NOT NULL FKs; unique index; service layer |
| INV-3 | An active assignment has a responsible owner **unless explicitly unassigned** (owner_user_id NULL allowed only with `unassigned` reason recorded at the change; unassigned assignments appear in a dashboard chip) | service layer + activity event |
| INV-4 | Lifecycle transitions only via the [11] §2 matrix; stage changes only in active/delivered; anything else rejected with `ps.error.invalid_transition` | single transition service (chokepoint), no direct state writes |
| INV-5 | At most one open next action per assignment | partial unique index ([25] §1) |
| INV-6 | Client deletion never destroys assignment records; person-client anonymization preserves numbers, money, history | C-4 + anonymization flow [16] §4 |
| INV-7 | Completion facts are attributed: tasks, next actions, assignments record done/completed time **and** actor together | service layer; columns set atomically |
| INV-8 | Money totals are derived at read time from entries; no stored editable total exists | schema (no such columns) + [21] |
| INV-9 | Every warning/risk/staleness/notification is reproducible from (stored data, org config, today); recomputation from scratch yields identical results | pure engine [13]; dedup keys [19] §3; property tests |
| INV-10 | `ps_deadline_changes` and `ps_activity_events` are append-only for all application roles | DB trigger + grants ([25] §5) |
| INV-11 | Official-deadline and internal-target edits occur only through the reasoned change action; every change is historised | no direct field write in API ([13] §5) |
| INV-12 | Terminal assignments (completed/cancelled) are read-only except: payment entries, files, and the owner 24 h revert — each write audit-logged | [11] §1, §3 |

## 2. Behavioural rules (consolidated from model docs — those texts are normative for detail)

**Lifecycle & stages** ([11], [12])
- BR-1: cancel requires reason; manager+ role.
- BR-2: deliver requires delivery date/method/recipient; auto-closes the
  open next action as superseded unless kept deliberately.
- BR-3: stage transitions free-form with soft guards (backward / >1-skip
  prompt for note; delivery-stage prompts deliver).
- BR-4: template/checklist edits never affect existing assignments (copy
  semantics); the explicit workflow-swap action is the only re-shaping path.
- BR-5: follow-up assignments link bidirectionally; pre-fill never copies
  deadlines, money, or dossier — new engagement, new facts.

**Next actions** ([14] N-1…N-9) — notably: completing prompts successor
(never silent); replacement supersedes (history kept); blocking reason ⇒
`blocked` signal without pausing any warning.

**Deadlines & engine** ([13]) — notably: date-only = end-of-day Sofia;
thresholds org-config validated attention > urgent ≥ 1; **no automatic
weekend/holiday deadline movement**; extension clears breach but history
remains; appointment-flagged future action suppresses staleness (I-4).

**Tasks** ([15] T-1…T-6) — notably: done tasks never delete; tasks never
block transitions.

**Documents** ([17]) — received requires file link or paper note; waived is
explicit; delivered/signed files on completed assignments never delete.

**Communications** ([18]) — logging is activity (resets staleness);
occurred_at editable (honest backdating), created_at immutable.

**Money** ([21]) — entries append-styled (edits by manager+ audit-logged);
payment_overdue only when agreed_price present.

**Notifications** ([19]) — one live notification per dedup key; breach
notifications not optable-out; digest collapse for staleness types;
auto-resolve on cause disappearance.

**Numbering** — `ps_number_sequences` per (org, year); format
`{PREFIX}-{YYYY}-{NNNN}`, prefix from org settings (default derived from
the org's assignment label, e.g. „ПОР"); gaps acceptable; numbers never
reused, never renumbered (NFR-PS-08).

## 3. Deletion policy (commissioned review: soft-delete vs archive vs purge)

| Object | Policy |
|---|---|
| Assignment | never hard-deleted; cancelled (state) or archived (derived filter, [11] §4) |
| Client | hard delete only if zero assignments ever; else deactivate/anonymize |
| Task | open: soft-delete; done: never |
| File | soft-delete (uploader same-day / manager+); delivered+signed on completed: never |
| Next action | never deleted — superseded/cancelled states are the history |
| Communication | edits by author same-day (audit-logged); no deletes (logbook) |
| Notification | acknowledged/resolved, never deleted (cheap rows, honest history) |
| Templates / service types | deactivate; hard delete only if never referenced |

## 4. Rule-change discipline

This document freezes *rules*, not code. Once implementation starts, a rule
change follows the repo's ADR/doc change process (docs/07 pattern):
proposal → PO decision → doc updated in the same PR as code. Tests cite
rule IDs; a failing rule test may never be "fixed" by deleting the rule
silently.
