# ADR-CS-003 — Deterministic core; AI as quarantined proposer

Status: Proposed (PO review) · Date: 18.07.2026

## Context

The system produces legal documents. AI is valuable for reading messy inputs
(scans, drawings, legacy files) and drafting prose, but hallucinated values
in an act are a legal hazard, and nondeterministic generation makes audits
impossible. The brief itself demands: "The core of the system is
deterministic… Never invent values."

## Decision

1. **The generation path contains no AI**: binding resolution, validation,
   and rendering are pure deterministic functions of (KB state, template
   version) — byte-reproducible, CI-verified (NFR-1).
2. **AI outputs are proposals, never facts**: extraction results live in a
   separate aggregate (`cs_extraction_proposals`) with schema validation,
   confidence, and source anchors. Only explicit human acceptance creates
   facts, recording provenance (method, model id, prompt revision).
3. Quarantine is **mechanically enforced**: AI clients exist only in
   ingestion adapters with no import path to KB write services
   (import-linter); accepted proposals require a resolution row + resulting
   fact linkage (DB constraint).
4. Confidence never gates automation — it orders review queues. No
   auto-acceptance tier exists in v1 ([20 §7](../20_AI_STRATEGY.md) defines
   the narrow future revisit condition).
5. AI-drafted narrative text (Act 15 part descriptions) enters the KB as a
   human-approved fact *before* any generation sees it — drafting assistance
   upstream, deterministic composition downstream.

## Consequences

- Extraction accuracy improves iteratively without ever risking the
  document path; deterministic per-type extractors progressively replace AI
  (measured, [16 §6](../16_DOCUMENT_EXTRACTION_PIPELINE.md)).
- Human review is a hard cost per imported document — accepted; it is the
  price of legal defensibility, and the review stream doubles as the
  evaluation dataset.
- The system remains fully functional with AI disabled (tenant opt-out) —
  extraction degrades to deterministic parsing + manual entry.
