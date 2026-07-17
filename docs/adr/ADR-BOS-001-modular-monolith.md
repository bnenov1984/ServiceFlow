# ADR-BOS-001 — Business OS Evolves as a Modular Monolith

Status: **Proposed (Phase 0 discovery, 17.07.2026) — awaiting PO review.
Not part of the frozen ADR-001…018 set; the BOS series is numbered separately
so it cannot be mistaken for accepted decisions.** ·
Source: docs/business-os/00–08 · Builds on: [ADR-001](ADR-001-modular-monolith.md) (Accepted)

## Context

The product direction is to grow further verticals (InvoiceFlow, StockFlow,
PropertyFlow, ProjectFlow, SportFlow, CRM) on ServiceFlow's foundations under
the working name Business OS. ADR-001 already fixed the modular-monolith style
for ServiceFlow and named "a second product sharing modules" as a
reconsideration trigger. This ADR answers that trigger in advance: the second
product does **not** cause a service split.

## Decision

Business OS is one deployable application for as long as the ADR-001 economics
hold: all modules (Core, shared, vertical) are built, tested, migrated, and
deployed together; boundaries are internal (packages + import-linter + data
ownership), never network boundaries. Multi-product support is achieved by
module activation as data (ADR-BOS-004), not by separate deployments per
product.

## Alternatives considered

- **Separate application per product, shared library Core** — version skew of
  the Core library across products; N deployments, N migration states for one
  maintainer. Rejected at current scale.
- **Microservices / product-per-service** — re-rejected for the same reasons as
  ADR-001, now with even less justification (shared tenant base, one dev).
- **Fork ServiceFlow per product** — fastest second launch, permanent
  divergence tax. Rejected; it is the outcome Business OS exists to prevent.

## Consequences

- One CI, one artifact, one migration history; a module is a directory, not an
  operational unit.
- Boundary discipline carries all the weight → dependency rules must be
  mechanical (docs/business-os/04).
- A hot module cannot scale independently — accepted; that is ADR-001's
  standing reconsideration trigger and it remains the exit criterion.

## Reconsideration triggers

Same as ADR-001 (real scale data), plus: a product requiring a materially
different release cadence or compliance boundary than the rest of the artifact.
