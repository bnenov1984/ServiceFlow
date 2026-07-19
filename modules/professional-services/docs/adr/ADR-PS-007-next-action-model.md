# ADR-PS-007 — Single-open next action

Status: **Proposed** · Date: 18.07.2026

## Context

The product's thesis is that "In Progress" hides the operational truth:
*what happens next, who does it, when*. Options considered: (a) plain
fields on the assignment (loses history and independent ownership);
(b) a queue of next actions (becomes a second task list; the pointer
semantics die); (c) deriving "next" from the task list (tasks describe
work breakdown, not commitment — the earliest-due task is often not the
next thing anyone will actually do).

## Decision

A dedicated **`NextAction`** entity; **at most one `open` per assignment**,
enforced by a partial unique index; full history via statuses
(`done`/`superseded`/`cancelled`). Completion always prompts the successor
choice — new action / stage change / explicit none (N-4, never silent).
Optional: reminder date, blocking reason (⇒ `blocked` signal),
appointment flag (⇒ staleness suppression I-4), link to a task (N-8;
completion offers, never forces, the counterpart). Absence of an open next
action on an active assignment is a first-class surfaced risk (I-2), not
an error — the system prompts, humans decide; nothing is auto-generated.

## Consequences

- The dashboard's most valuable bucket ("без следваща стъпка") is
  trivially computable and impossible to game.
- The assignment's action history doubles as its operational heartbeat.
- One-pointer discipline forces prioritisation conversations a queue
  would let firms avoid — a deliberate product opinion; if pilots prove
  it wrong, the schema tolerates relaxation (drop the partial index), but
  the default stays opinionated.
