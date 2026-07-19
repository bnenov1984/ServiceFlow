# PS-13 — Deadline and Reminder Engine

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

The engine is the product's differentiator and therefore its most rigorously
specified part. Governing principle (NFR-PS-05): **every output is a pure
function of stored data + org config + "today"** — reproducible, clock-frozen
testable, with no hidden state and no AI.

## 1. Date taxonomy (no generic deadline field — 09 §3.3)

| Date | Storage | Semantics |
|---|---|---|
| Official deadline | `official_deadline_on date` + optional `official_deadline_time time` | externally binding; the breach axis |
| Internal target | `internal_target_on date` | firm's own margin; earlier warning stream |
| Next-action due | `ps_next_actions.due_on date` | operational cadence |
| Task due | `ps_tasks.due_on date` | granular work dates |
| Appointment | next action/task with `is_appointment` | fixed moment; prep anchor, not breach |
| Reminder | `reminder_on date` on next action (+ `ps_reminders` P for recurring) | fires regardless of due state |
| Payment due | `payment_due_on date` on assignment | money stream ([21]) |
| Received / planned start / completed | assignment columns | inputs to staleness, not warnings |

## 2. Timezone rules (Europe/Sofia)

1. All instants stored UTC; all date-only fields stored as `date`.
2. A date-only deadline means **23:59:59 Europe/Sofia of that date**; an
   exact-time deadline means that wall-clock time in Europe/Sofia.
3. "Today" = current date in Europe/Sofia, computed at exactly one code
   point (`ps_today()`), injected everywhere (tests freeze it).
4. Day arithmetic is calendar-date arithmetic on Sofia dates — DST
   transitions cannot shift a boundary because boundaries are dates, not
   23-/25-hour offsets. Timezone tests pin the DST weekends ([32] §T-3).
5. If the platform later serves other timezones, `Europe/Sofia` becomes an
   org setting; no schema change (dates stay dates) — recorded assumption
   A-4 in [36].

## 3. Risk states (official deadline stream)

Pure function `deadline_risk(deadline_on, deadline_time?, state, today, cfg)`:

| Condition (defaults) | Risk state | BG label |
|---|---|---|
| state ∉ {active} → | *(stream off — [11] §5)* | — |
| days_left > cfg.attention (7) | `normal` | В срок |
| cfg.urgent (3) < days_left ≤ cfg.attention | `attention` | Наближаващ срок |
| 0 < days_left ≤ cfg.urgent | `urgent` | Спешно |
| days_left = 0 | `critical` | Днес |
| days_left < 0 | `breached` | Просрочено |

`days_left = deadline_on − today` (calendar days). Exact-time deadlines: on
the due day, past the time ⇒ `breached` same day. The internal target runs
the same function with its own (earlier) output rendered as the internal
stream: UI shows the worse of the two, always labelled with which deadline
produced it. No deadline entered ⇒ risk `none` + surfaced in the
"без краен срок" filter (a deliberate visibility, not silence).

Every risk state renders as label + icon + filter value — **never colour
alone** (NFR-PS-18). Thresholds: org config `{attention_days, urgent_days}`
validated `attention > urgent ≥ 1`; per-assignment override (P, FR-PS-041)
uses identical semantics.

## 4. Weekends and public holidays

- A per-year Bulgarian holiday table (fixed holidays + movable Easter +
  government compensatory days) ships as **module data**, org-visible,
  owner-editable (firms may add local non-working days).
- **MVP uses the calendar only for (a) display badges — "срокът е в
  неделя/на празник" at entry time and in lists — and (b) working-day
  staleness arithmetic (§6). It never moves a deadline** (ADR-PS-008): an
  entered date is the binding date; whoever set it (court, bank) owns its
  weekend semantics, not the module.
- Deferred (F): optional per-org rule "warn N *working* days ahead" —
  threshold arithmetic in working days. Not default, ships only on demand.

## 5. Deadline changes

- `official_deadline_*` and `internal_target_on` edits go through a
  dedicated "промяна на срок" action: new value + **mandatory reason**
  (official) / optional (internal) → append `ps_deadline_changes` row (old,
  new, reason, actor, at) → activity event → notification to owner if
  changed by someone else. Direct field edit does not exist in the API.
- History renders on the assignment (S-4) to whoever can see it — a
  deadline moved five times is itself a risk signal humans should see.
- Extending past a today-breached state clears `breached` (correct: the
  binding date changed); the history keeps the shame visible.

## 6. Inactivity & stagnation signals (deterministic, MVP)

`last_activity_at` = latest activity event (any child write counts; pure
reads don't). Signals evaluated per active assignment (I-6 for delivered):

| ID | Signal | Rule (defaults, org-configurable) |
|---|---|---|
| I-1 | `stale` | working_days(last_activity_at → today) ≥ 5 |
| I-2 | `no_next_action` | no open next action |
| I-3 | `next_action_overdue` | open next action due_on < today |
| I-4 | *suppression rule* | a future-dated appointment-flagged next action suppresses I-1 (Стоян's hearing months away is *not* stale) — the appointment is the activity |
| I-5 | `waiting_too_long` | current stage category waiting_client/waiting_documents AND working_days(stage_entered_at → today) ≥ 10 |
| I-6 | `undelivered_closeout` | state delivered AND days(delivered_at → today) ≥ 14 |
| I-7 | `never_started` | at first stage AND no activity since creation ≥ 5 working days |

All are computed set-based over indexed columns; each carries label + filter
+ dashboard bucket. Future AI (F, [22 principles]): narrative risk summaries
and *suggested* next actions — flagged as suggestions, never state.

## 7. Reminders and the engine's outputs

- The engine **derives states**; the notification model ([19]) decides who
  hears about which state transitions, with dedup/ack/snooze. Snoozing a
  notification never changes the underlying state (the dashboard still
  counts it — control stays honest; muting rules live in [19] §5).
- Explicit reminders (`reminder_on`) fire once on their date at the morning
  run; recurring reminders are P (FR-PS-046) with a `ps_reminders` table.
- Evaluation runs: (a) morning per-tenant job (platform job pattern
  ADR-006); (b) on-write recompute for the touched assignment (instant
  feedback). Both idempotent (NFR-PS-14): recomputation from scratch always
  yields the same states — the job emits *notifications for transitions*,
  the states themselves are never persisted as authority (INV-9).

## 8. Worked boundary examples (normative for tests, [32] §T-2)

Config: attention 7, urgent 3. Today = 18.07.2026 (Sofia).

| Official deadline | days_left | Risk |
|---|---|---|
| 28.07.2026 | 10 | normal |
| 25.07.2026 | 7 | attention |
| 21.07.2026 | 3 | urgent |
| 19.07.2026 (Sunday) | 1 | urgent + weekend badge |
| 18.07.2026, no time | 0 | critical (all day) |
| 18.07.2026 17:00, now 17:01 Sofia | 0 | breached |
| 17.07.2026 | −1 | breached |

DST pin: deadline 29.03.2026 (clocks spring forward 03:00→04:00): on
28.03.2026 days_left = 1 — the missing hour must not produce 0 or 2.
