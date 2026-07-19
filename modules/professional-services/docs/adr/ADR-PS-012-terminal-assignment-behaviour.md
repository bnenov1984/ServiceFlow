# ADR-PS-012 — Terminal behaviour: no reopen, linked follow-ups

Status: **Proposed** · Date: 18.07.2026

## Context

The commission asks whether terminal assignments may reopen or whether a
linked follow-up should be created, with documented consequences. Domain
reality: follow-on engagements are genuinely *new* engagements
(допълнителна експертиза, updated valuation, next acts batch) with new
deadlines and often new money; true errors ("clicked complete
accidentally") also happen; and delivered work legitimately bounces back
for corrections.

## Decision

1. `completed` and `cancelled` are **terminal — no reopen**. Follow-on
   work = a **new assignment linked** `follow_up_of` (bidirectional
   rendering), pre-filled with client/contact/type/details but never
   deadlines, money, or dossier.
2. `delivered → active` ("връщане за корекции", reason required) is a
   normal, non-terminal move — the corrections loop is not reopening.
3. **24-hour owner-only revert** of a terminal transition, audit-logged
   with reason — the honest escape hatch for genuine mistakes, narrow
   enough not to erode terminal semantics (BR-2-unlock philosophy from
   ServiceFlow, mechanics own).
4. Terminal records are read-only except payment entries and files
   (late invoices/receipts arrive after close-out), each write
   audit-logged (INV-12).

## Consequences

- Counts show two assignments where the world had two engagements —
  correct, and stated so support can answer it.
- History is trustworthy: a completed 2026 assignment reads the same in
  2028.
- The 24 h window is a deliberate judgment call the PO should confirm;
  alternatives (no revert at all / manager-wide revert) are one-line
  changes if vetoed.
