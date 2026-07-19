# PS-14 — Next Action Model

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

"In Progress" answers nothing operationally. The next action — *what happens
next, by whom, by when* — is this product's beating heart (ADR-PS-007).

## 1. Entity

`NextAction`: description (required, short free text), owner (user, required,
defaults to assignment owner), `due_on` (required — an action without a date
is a wish), optional `reminder_on`, optional `blocking_reason` (free text —
its presence = the `blocked` signal), `is_appointment` flag, optional
`task_id` link, status `open | done | superseded | cancelled`, done_at/by.

**At most one `open` per assignment** (partial unique index). Why one, not a
queue: a queue is a task list — we have tasks ([15]). The next action is a
*pointer*, and a pointer to three things points at nothing. The history rows
(`done`/`superseded`) stay — they read as the assignment's operational
heartbeat ("what we did, step by step").

## 2. Rules

| # | Rule |
|---|---|
| N-1 | Applies to `active` assignments; `delivered` may optionally carry one (e.g. hearing after submission, "изчакай потвърждение"); terminal states force-close open actions ([11] §2) |
| N-2 | No open action ⇒ signal `no_next_action` (I-2): dashboard bucket, list badge, notification after a grace period (default: immediately visible, notified next morning run) |
| N-3 | Overdue action (due_on < today) ⇒ I-3: badge + notification to action owner; escalation to manager after N days (default 2) — [19] §4 |
| N-4 | Completing an action opens the successor dialog (J-3 ⚡): enter next \| jump to stage change \| explicitly none ("съзнателно без следваща стъпка" — recorded, still lands in the bucket). Never silent-close |
| N-5 | Replacing an open action supersedes it (status `superseded`, history kept) — no editing an open action's essence into a different action; small edits (typo, date) are edits, owner change is an edit; the heuristic: edit keeps identity, replace changes intent. UI offers both, both audit-logged |
| N-6 | `blocking_reason` present ⇒ `blocked` signal; blocked actions still have due dates (the date to chase the blocker) — blocking never pauses warnings, it explains them |
| N-7 | Appointment actions (`is_appointment`): due_on = the appointment date; suppress staleness (I-4); completing prompts "какво следва?" like any action |
| N-8 | Optional task link: "this action = do task X" — completing either offers to complete the other (never automatic) |
| N-9 | Creation prompt after intake (J-1 step 6) with per-service-type suggested first action text (part of service-type defaults, P if not trivial in MVP build) |

## 3. Duplicate-date avoidance (commissioned concern)

The next-action `due_on` does not duplicate assignment deadlines: it is the
date of the *next step*, deadlines are dates of the *result*. Guard rails:

- UI shows official deadline + internal target beside the due-date field;
  entering a due after the official deadline warns (does not block).
- An appointment already tracked as a task is linked (N-8), not re-typed.
- Nothing copies deadlines into actions automatically.

## 4. Waiting states vs active work (commissioned concern)

Waiting is expressed by **stage category** (waiting_client /
waiting_documents), not by the next action. In a waiting stage the next
action is the *chase*: "Позвъняване за скицата — петък". So: stage says
*why nothing moves*, next action says *when we poke it*. I-5 catches waiting
stages whose chase never happens; N-6 `blocked` catches active work stuck on
an external dependency that is not client/documents (e.g. "чакаме депозит").

## 5. What this model refuses to be

- **Not auto-generated:** the system suggests (deterministic templates per
  service type; future AI suggestions clearly labelled) but a human always
  confirms — an auto-created action nobody meant is worse than the empty
  bucket, because it silences the signal.
- **Not a workflow driver:** completing actions never advances stages.
- **Not a dependency graph:** "optional dependency" from the commission is
  served by the task link (N-8) + blocking reason (N-6); a real DAG is
  refused ([02] §2.3, F-class).
