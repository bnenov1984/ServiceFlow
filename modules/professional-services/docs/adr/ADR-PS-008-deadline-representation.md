# ADR-PS-008 — Deadline representation, Europe/Sofia, no auto-shifting

Status: **Proposed** · Date: 18.07.2026

## Context

Deadline management is the differentiator; it must be exactly predictable
or firms keep their paper calendars. Design questions: one generic
deadline table vs typed fields; date vs datetime; weekend/holiday
semantics; mutability.

## Decision

1. **Typed, separate date fields** per concept (official, internal
   target, next-action due, task due, appointment, reminder, payment due)
   — a polymorphic `ps_deadlines` table was considered and rejected
   (PS-09 §3.3).
2. **Date-only by default**, meaning end-of-day **Europe/Sofia**; optional
   exact time for the official deadline only. All instants stored UTC;
   dates stored as `date`; the Sofia boundary conversion lives in exactly
   one code location; day arithmetic is calendar-date arithmetic (DST-
   immune by construction).
3. **No automatic deadline movement, ever** — weekends/holidays produce
   badges and can inform *warnings*, never shift the binding date. The
   entered date is the deadline; its issuer (court, bank) owns its
   calendar semantics.
4. **Reasoned-change chokepoint:** the two guarded dates change only via
   an action requiring a reason (official) and historising every change
   (ADR-PS-006 layer 2). Extension clears breach; history remains.
5. Risk thresholds (`attention`/`urgent` days) are org config with
   validated ordering; the risk function is pure and clock-frozen-testable
   (PS-13 §3, §8 is executable spec).
6. Bulgarian holiday calendar ships as per-year module **data**
   (org-editable); MVP uses it for display + working-day staleness
   arithmetic only. Working-day *threshold* arithmetic and statutory-term
   calculation are deferred with named triggers.

## Consequences

- Determinism is testable end-to-end (INV-9); support can reproduce any
  warning from an export.
- Users who expect court-style term arithmetic must enter the resulting
  date themselves in MVP — honest, documented, and the calculator remains
  a clean future addition.
- Multi-timezone future = one org setting, no schema change (A-4).
