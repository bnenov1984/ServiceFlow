# ADR-PS-010 — Cross-module integration: opaque links + contracts

Status: **Proposed** (contract details **Deferred** until both modules
have code) · Date: 18.07.2026

## Context

Professional Services must link assignments to Construction Documentation
projects (engagement wrapper ↔ specialised production) without merging
bounded contexts. Platform rules: contracts over reach-ins (ADR-BOS-003),
one owner per table (BOS-05), no cross-module FKs.

## Decision

- **Link representation:** `ps_assignment_links` rows with
  `(target_module, target_ref)` as an **opaque reference** — no FK, no
  copied data; dangling links render degraded, never crash. The link is
  engagement metadata, so PS owns the row; CS reads it via PS's contract.
- **Interaction:** typed application contracts both ways (PS-29 §3 lists
  the proposed shapes: project picker/summary/deliverable-fetch from CS;
  assignment-ref/links-for from PS). No file copying between modules;
  CS deliverables render via reference.
- **Events:** optional, informational only; no module ever changes
  another module's state automatically.
- **Activation:** integration UI appears only when both modules are
  active for the company (BOS-06 `optional` dependency).
- This pattern is the module's **general** answer for any future
  cross-module relation (commercial invoicing uses the same shape via
  `external_ref` on payment entries — PS-21 §3).

## Consequences

- Neither module can break the other by schema change; contracts are the
  entire coupling surface.
- Contract signatures are deliberately **not frozen** here (the
  counterpart is docs-only today — assumption A-7); freezing them now
  would be invented certainty. Tracked as PS-36 Q-4.
