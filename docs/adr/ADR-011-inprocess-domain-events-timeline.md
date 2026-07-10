# ADR-011 — In-Process Domain Events Feeding the Timeline

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §3, 01 §5

## Context
Every meaningful business change must produce a trustworthy TimelineEvent in the same
business transaction (01 §BR-5). The domain event list (01 §5) also defines future
notification hooks (V1.5 SMS/Viber) — without building eventing infrastructure now.

## Decision
Synchronous in-process domain events: domain modules publish typed events; the
`timeline` module subscribes and writes TimelineEvents **inside the same database
transaction** as the originating change. Other subscribers (search shadow updates,
future notification outbox) register through the same dispatcher. No broker, no
async eventing, no event sourcing.

## Alternatives considered
- **Direct timeline writes from each module** — works, but scatters the "what is
  history-worthy" decision and makes future subscribers (notifications) invasive.
  Rejected.
- **Event sourcing** — the timeline is an *output* of state, not the source of
  truth; sourcing would multiply complexity for zero V1 value. Rejected (blueprint
  explicitly warns against it).
- **Async events via broker/outbox now** — infrastructure for subscribers that don't
  exist yet. Rejected; an outbox pattern is the documented V1.5 extension for
  notifications.

## Consequences
- **Advantages:** timeline completeness is structural (publish once, recorded
  always); transaction guarantees mean no phantom history; the event catalog is the
  future integration surface.
- **Disadvantages:** synchronous subscribers add latency to writes — trivial at our
  volumes; slow work (thumbnails) goes to jobs (ADR-006), not subscribers.
- **Risks:** event sprawl. Mitigation: the event catalog in 01 §5 is normative;
  additions require domain-doc updates.

## Reconsideration triggers
V1.5 notifications add a transactional outbox consumed by jobs; SaaS scale may move
the dispatcher behind a queue port — the publishing contract is designed not to change.
