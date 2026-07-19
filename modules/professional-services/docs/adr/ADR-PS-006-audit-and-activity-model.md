# ADR-PS-006 — Three-layer audit/activity model, append-only

Status: **Proposed** · Date: 18.07.2026

## Context

The commission demands complete audit history, immutable to ordinary
users, with deadline changes and completions auditable. The platform
provides a Core technical AuditLog (security events) and has proven an
append-only timeline pattern (DB trigger) inside ServiceFlow. BOS-02 keeps
business timelines module-owned (group C/D).

## Decision

Three distinct layers (PS-30 §2):

1. **`ps_activity_events`** — business history of every assignment,
   module-owned, append-only via DB trigger (ServiceFlow's proven
   mechanism, reimplemented), fed by the module's own domain events;
   drives `last_activity_at` and the S-4 История feed.
2. **`ps_deadline_changes`** — dedicated forensics for the two guarded
   dates, written only by the reasoned-change chokepoint (INV-11),
   append-only.
3. **Core `audit_log`** — platform security events (role changes,
   terminal reverts, anonymization, exports) via Core's mechanism.

No event sourcing: events/history are projections; tables remain the
source of truth (platform ADR-011 stance reaffirmed).

## Consequences

- "Who changed the deadline and why" is answerable forever, cheaply.
- Append-only enforcement is testable at the DB level (T-7) — immutability
  does not depend on application discipline.
- Three layers cost three write paths; the split prevents both
  over-exposure of security events and under-exposure of business history
  — the platform's own reasoning (BOS-05 §3), inherited deliberately.
