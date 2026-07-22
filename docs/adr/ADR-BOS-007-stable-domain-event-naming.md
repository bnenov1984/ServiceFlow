# ADR-BOS-007 — Stable, Module-Namespaced Domain Event Names

Status: **Accepted** (naming & versioning discipline only — no code change
required) · Date: 21.07.2026 · Source: PO review of docs/business-os +
modules/professional-services (this session)

## Context

ServiceFlow already publishes domain events (`part_added`, `task_created`,
`task_completed`, `attachment_added`, …) over the in-process bus
(ADR-011), unprefixed, because only one vertical existed when they were
named. BOS-02 already flags one related leak (`DomainEvent.order_id`) for
cleanup "at the next natural touch" — but that touch is about the
envelope, not the type names.

Two problems grow with every new vertical if event type names stay ad
hoc:

1. **Collision.** ServiceFlow already owns `task_completed` for repair-order
   tasks. Professional Services' own task model (PS-15) wants the
   identical *word* for an unrelated entity. The bus dispatches events
   unfiltered to all subscribers (BOS-06 `subscribes: [all]`) — a naming
   collision is a silent double-subscription bug, not a compile error.
2. **Instability.** Once any consumer subscribes to a *name* — the
   module's own timeline-equivalent today, and, per the PO's stated
   rationale, future AI/search/notification consumers years from now —
   silently renaming that event breaks the consumer with nothing to catch
   it. Names are cheap to fix before consumers exist and expensive after.

## Decision

1. **Every domain event type a module publishes is module-namespaced**:
   `{module_id}_{subject}_{past_tense_verb}`, snake_case — matching the
   platform's existing casing convention (no PascalCase/camelCase
   introduced). Example: `ps_assignment_created`, not `AssignmentCreated`.
2. **ServiceFlow's currently unprefixed events are grandfathered, not
   renamed by this ADR.** Renaming touches every publisher and the
   timeline subscriber for zero functional gain today. Deferred to "the
   next natural touch" of that code — the same phrasing, and plausibly the
   same touch, as the `order_id` leak already scheduled in BOS-02.
3. **Once a module's docs publish an event catalogue** (the `§ Domain
   events` pattern already used in PS-09 §5 and in the BOS-06
   `events.publishes` field), **its type names are a stable contract**:
   adding new event types is free; renaming or removing a published type
   follows the docs/07-style change process (proposal → PO decision →
   docs and code updated together in the same PR) — the same discipline
   Professional Services' own business rules already commit to (PS-26 §4).
4. **This is a naming and versioning discipline only.** It does not imply
   event sourcing, guaranteed delivery beyond the existing in-process bus,
   or a schema-registry infrastructure. Payloads remain "ids + primitives
   only" (existing BOS-06 rule), unchanged.
5. **New modules declare their event catalogue in their Phase-0 docs,
   before implementation** — exactly what Professional Services already
   did in PS-09 §5. This ADR **ratifies that choice as now-mandatory
   platform-wide**, so no rework is required there.

## Alternatives considered

- **(a) Leave event names ad hoc, resolve collisions if they occur** —
  rejected: the failure surfaces silently at runtime (unfiltered dispatch
  means no error, just a wrong subscriber firing), exactly the risk named
  above.
- **(b) A central event-name registry service validating names at publish
  time** — rejected: infrastructure solving a problem an explicit
  published list already solves (BOS-00 anti-goal #4 — "a
  registry/reflection/discovery mechanism where an explicit list works").

## Consequences

- Zero code changes today. Professional Services' event catalogue (PS-09
  §5) already complies — no rework needed.
- ServiceFlow's own events remain technically non-compliant until their
  scheduled touch — an accepted, tracked gap, not silently ignored.
- Future modules (Construction Documentation, CRM, …) get a collision-free
  naming rule for free, and future AI/analytics consumers (per the
  commissioned professional-services vision's own no-AI-in-core-loop,
  AI-as-reader stance) get a vocabulary that will not move under them.
