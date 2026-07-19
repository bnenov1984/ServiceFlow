# ADR-CS-006 — Module-owned engines; extraction to platform deferred

Status: Proposed (PO review) · Date: 18.07.2026

## Context

This module builds engines that *sound* platform-shaped: templates, rules,
workflow, document generation, provenance. ServiceFlow has adjacent
machinery (PDF documents, numbering, timeline). The temptation to build
"the Business OS document platform" now is exactly what BOS-00 §7
(anti-goals: abstraction with one consumer) and the pragmatism directive
forbid; BOS-08 Phase 6 already defines the extraction discipline.

## Decision

1. Template engine, rules engine, workflow/state machines, generation
   pipeline, provenance model, extraction pipeline: **all owned by
   `construction_supervision`**, built to this module's concrete needs.
2. No shared "document platform", "rules platform", or "workflow platform"
   package is created, and `construction_supervision/contracts.py` stays
   empty until a real external consumer exists.
3. The module keeps an **extraction watchlist**
   ([24 §5](../24_INTEGRATION_WITH_BUSINESS_OS.md)) recording where its
   implementations converge/diverge with ServiceFlow's — the evidence file
   for future BOS Phase 6 proposals (candidates BOS already names: document
   generation plumbing, numbering, attachments).
4. Interfaces likely to be extracted later (renderer, storage usage,
   numbering) are kept *clean within the module* — extraction-friendly, not
   extracted.

## Consequences

- Some deliberate duplication with ServiceFlow (each has document rendering,
  numbering, timeline projection) — the BOS-08 Phase 5 rule working as
  intended: duplication is data for Phase 6, not a defect.
- Phase 6 extractions, when they come, are PO-gated mini-projects with two
  concrete implementations to generalize from — not speculation.
