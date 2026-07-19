# ADR-PS-009 — Module-owned deterministic in-app notifications

Status: **Proposed** · Date: 18.07.2026

## Context

The platform has no notification capability (BOS-02 group D: "do not
design in Phase 0" — platform-side). This module cannot ship without
notifications (deadline warnings are the product). Options: (a) build a
platform notification service first — violates build-own-or-wait and
blocks the module on platform work with one consumer; (b) build
module-owned notifications shaped for later comparison — chosen.

## Decision

- **`ps_notifications`**, module-owned, in-app only in MVP; message-key
  payloads (never prose), severity, per-recipient rows.
- **Deterministic generation** by the same evaluation paths as the
  deadline engine (morning per-tenant job + on-write recompute);
  idempotence via a **unique dedup key per live notification**; state
  progressions mint new keys; auto-resolve on cause disappearance.
- Anti-overload by design: daily digest collapse for staleness-class
  types; individual delivery only for deadline/breach classes; escalation
  limited to breach + persistent overdue; org defaults + per-user
  per-type opt-out, breach excepted.
- Future channels (email/desktop) append to `delivered_channels` riding
  the Етап-3 outbox — the record model does not change.

## Consequences

- The platform gains its first concrete notification implementation —
  extraction evidence for the day a second module needs one (R-FUT,
  PS-27).
- Notification correctness is unit-testable without time simulation
  hazards (T-5); "same evaluation twice ⇒ no duplicates" is a hard test.
- In-app-only MVP means users must open the app — acceptable because the
  dashboard *is* the morning ritual (J-2); channel expansion is P-class
  with a real trigger.
