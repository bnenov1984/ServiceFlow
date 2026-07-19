# ADR-CS-002 — Single source of truth; documents are generated views

Status: Proposed (PO review) · Date: 18.07.2026

## Context

Supervision documents repeat the same facts dozens of times; the sample
corpus shows real drift (contradictory cadastral identifiers inside one
technical passport). The product's founding premise is eliminating
duplication — but signed legal documents must never change retroactively,
which naive "everything is a live view" designs violate.

## Decision

1. Every project fact has **exactly one authoritative, writable location**
   (typed entity attribute or KB fact — [10 §3](../10_DATA_MODEL.md)).
   Documents bind to facts; they never own copies while in draft.
2. **Issuance freezes a snapshot**: the resolved rendering context (fact
   versions, participant attributes, template version, file hash) is copied
   into the issued document version and becomes immutable. This is the only
   sanctioned duplication class: *frozen history, never live state*.
3. Divergence between live facts and issued snapshots is detected and
   surfaced (info findings), resolved only by formal supersede or waive —
   never by silent reconciliation in either direction.
4. A PR introducing a second writable location for an existing fact is a
   review-blocker (CS-01 guardrail 2).

## Consequences

- Generated drafts cannot disagree with each other — consistency by
  construction; the rules engine focuses on ingestion and issuance
  boundaries ([19 §3](../19_VALIDATION_AND_CONSISTENCY.md)).
- Storage cost of snapshots is accepted (small JSONB per issued doc;
  documents per project number in the dozens).
- "Change one value, update every document" holds for drafts and is
  *deliberately false* for issued documents — matching legal reality.
