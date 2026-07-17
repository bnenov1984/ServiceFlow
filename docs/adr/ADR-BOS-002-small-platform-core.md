# ADR-BOS-002 — Small Platform Core

Status: **Proposed (Phase 0 discovery, 17.07.2026) — awaiting PO review; not
part of the frozen ADR set** · Source: docs/business-os/02 (classification),
00 §4 (definition)

## Context

Every platform effort faces the same failure mode: the shared layer accretes
everything that *might* be reusable and becomes a second product nobody asked
for. ServiceFlow already contains a de-facto platform layer that is genuinely
domain-neutral (`identity/`, `platform/`, `shared_kernel/` — see
docs/business-os/01 §10), and a long tail of capabilities that merely look
reusable (tasks, attachments, contacts, timeline, document generation).

## Decision

Business OS Core is limited to: tenancy (company, tenant context, chokepoint,
RLS binding), identity & sessions (users, PIN, CSRF, owner flag), technical
audit log, technical primitives (UUIDv7 ids, db base, neutral event bus,
storage port, text normalization), the i18n/error-envelope mechanism, and
platform services (health; per Етап 3: registration, subscriptions/billing,
admin console, export envelope, jobs).

Admission of anything else requires **both**: (1) two real modules needing it,
or the capability being inherently platform-level; and (2) zero vertical
vocabulary in its code. Hypothetical future products satisfy neither.
Everything in classification groups B/C/D (docs/business-os/02) stays out of
Core; group D items remain inside ServiceFlow until a second real module proves
reuse.

## Alternatives considered

- **Broad core** (tasks, attachments, contacts, notifications, custom fields as
  platform capabilities) — maximizes hypothetical reuse, guarantees speculative
  abstraction with one consumer each. Rejected — violates the pragmatism
  directive that is CLAUDE.md hard rule 1.
- **No named core** (keep everything ServiceFlow, refactor when module #2
  arrives) — cheapest today; but the already-neutral layer then risks
  absorbing vertical vocabulary (the `DomainEvent.order_id` leak shows the
  drift is real). Rejected — naming and lint-guarding the existing boundary
  costs days.

## Consequences

- Core changes slowly and can be held to a higher review bar (R3/R8 rules).
- Module #2 will find Core lacking things it wants (e.g. generic activity
  feed) — by design; it builds its own, and extraction happens from two
  implementations (roadmap Phase 6).
- The word "Core" gets a testable definition instead of being a status symbol.

## Reconsideration triggers

A second real module in production duplicating a capability with materially
identical semantics (the Phase-6 extraction path); or Core failing to cover
something *every* module demonstrably needs.
