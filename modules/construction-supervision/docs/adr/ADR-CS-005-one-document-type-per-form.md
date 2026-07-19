# ADR-CS-005 — One document type per act form; bundles are ingestion artifacts

Status: Proposed (PO review) · Date: 18.07.2026

## Context

The sample corpus contains a combined Word file (актове-къща.docx) holding
~20 acts of forms обр. 12, 7, and 8 in one document — the firm's practical
packaging for a project's structural phase. The initiating task explicitly
requires Act 14 to be modeled independently and warns that the combined file
must not shape the architecture. The corpus also proves the danger: one act
in the bundle carries an обр. 7 header over обр. 12 body text — bundling
invites cross-contamination.

## Decision

1. **Every act form is an independent document type**: own registry entry,
   template pair, rule set, required participants, workflow, numbering, and
   generated DOCX output. This holds for Act 12, Act 14, Act 15, the
   Technical Passport, and every future form — no "generic act with a type
   field" template, no shared rule set by default.
2. Shared *structure* is factored at the manifest level only (the common
   header block include — [11 §1.4](../11_DOCUMENT_MODEL.md)), never by
   merging types.
3. **Combined source files are split at ingestion** into per-act source
   sections, each classified to its own type ([16 §2](../16_DOCUMENT_EXTRACTION_PIPELINE.md)).
   The bundle remains one stored file (evidence integrity) with N logical
   documents layered over it.
4. Generated output is one file per document instance. Convenience bundles
   (print packet for a phase) are a later *export* feature composing issued
   documents — never a generation-time merge.

## Consequences

- Adding/changing one form never risks another (regulatory amendments touch
  one type's artifacts).
- The обр.7/обр.12 contamination class becomes structurally impossible in
  generated output and *detectable* in ingested legacy files
  (`cross_ref_match` rule).
- Slight duplication across manifests of similar forms — accepted, and
  mitigated by manifest includes, not by type merging.
