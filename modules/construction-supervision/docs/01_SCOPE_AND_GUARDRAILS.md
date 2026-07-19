# CS-01 — Scope and Guardrails

Status: **Draft for PO review** · Date: 18.07.2026

The brief asks for "the industry's reference software". The Business OS
pragmatism directive (CLAUDE.md rule 1) forbids enterprise patterns without a
concrete problem. This document reconciles the two: *reference-quality domain
model, ruthlessly small delivery increments.* Every subsystem below is scoped
to the evidence in the sample set, not to hypothetical large clients.

## 1. In scope (module lifetime)

- Project registry: construction projects, sites, permits, categories.
- Participant registry: firms and persons with their legal attributes
  (ЕИК, ДНСК удостоверение, КИИП/КАБ registration, diplomas, validity dates).
- Knowledge base of project facts with provenance and confidence.
- Document ingestion: PDF, DOCX, scanned images → classified source documents.
- Extraction pipelines: deterministic first, AI-assisted second, human-confirmed
  always.
- Drawing repository and drawing analysis (vector-first; phased — see roadmap).
- Quantity calculation: concrete, reinforcement, formwork from structural data.
- Template engine + DOCX generation for the act family and technical passport.
- Rules engine: field validation, cross-document consistency, chronology,
  completeness (missing acts/certificates).
- Workflow engine: construction lifecycle phases, per-document-type state
  machines, phase gates.
- Digital dossier: complete, ordered, exportable project file with audit trail.

## 2. Out of scope (explicit, with reasons)

| Excluded | Reason |
|---|---|
| CAD/BIM authoring, structural analysis | We read outputs (drawings, schedules); tools like Tower already exist. |
| Budgeting/procurement/invoicing for builders | Different buyer; Business OS commercial module may cover invoicing later. |
| Generic document management for arbitrary files | Files are only sources of facts or dossier members. |
| Municipal/ДНСК e-government integration | No stable public APIs; revisit when they exist ([29_RISKS](29_RISKS_AND_OPEN_QUESTIONS.md) Q7). |
| Qualified e-signature (КЕП) workflows in MVP | Печат-и-подпис is the current practice; e-signature is a later phase ([28_ROADMAP](28_IMPLEMENTATION_ROADMAP.md)). |
| Editing the *legal wording* of act forms | Normative text comes from Наредба №3 templates; only data and предвидени свободни полета vary. |
| Multi-language generated documents | Acts are Bulgarian legal documents; bg only. |

## 3. Guardrails (review-blockers, inherited and new)

1. **Business OS hard rules apply unchanged**: tenant isolation (ADR-016),
   UUIDv7 + company_id (ADR-013), message-key i18n (ADR-015), import-linter
   boundaries (ADR-001/BOS), no PII in logs.
2. **SSOT rule (ADR-CS-002)**: a fact has exactly one authoritative row. A PR
   that stores the same real-world value in two writable places is rejected.
3. **Determinism rule (ADR-CS-003)**: no AI call in the generation path.
   Generation = knowledge base + template version → same bytes, every time.
4. **Word-is-dumb rule (ADR-CS-004)**: no logic in .docx files. A template
   change that encodes a condition inside Word instead of the manifest is
   rejected.
5. **One-type-per-document rule (ADR-CS-005)**: every act form (обр. 12, 14,
   15…) is its own document type with its own template, rules, workflow, and
   participants — even when a source file bundles several (the combined
   акове-къща.docx sample is an *ingestion* problem, not a modeling license).
6. **Evidence rule**: a document type, rule, or pipeline stage enters the
   backlog only with a real sample or a named client need behind it. "Acts
   exist for bridges too" is not a backlog item.
7. **Module modesty rule**: nothing this module builds is declared "platform"
   by itself. Extraction into Business OS shared modules follows BOS-08
   Phase 6 (two concrete implementations) — see
   [24_INTEGRATION_WITH_BUSINESS_OS.md](24_INTEGRATION_WITH_BUSINESS_OS.md).

## 4. Sizing assumptions

- Firms of 1–10 users; tens of active projects; hundreds of documents and a
  few GB of files per project (drawings dominate).
- Single maintainer development reality — prefer boring technology, reuse
  Business OS infrastructure, no new runtime services without an ADR.
- Bulgarian regulatory regime only.

## 5. Assumption challenges (as requested by the brief)

- *"Import everything, extract everything"* — challenged. For a new project
  started **in** the system, most facts are entered once by hand faster than
  they can be extracted and reviewed. Extraction earns its complexity on
  **legacy/mid-stream projects** and on third-party inputs (permits,
  certificates, drawings). MVP therefore leads with structured entry +
  generation, not OCR ([27_MVP_DEFINITION.md](27_MVP_DEFINITION.md)).
- *"Read construction drawings"* — challenged and phased. Full drawing
  understanding is research-grade; **schedule tables and title blocks** in
  vector PDFs are tractable and carry most of the quantity data
  ([17_DRAWING_ANALYSIS_PIPELINE.md](17_DRAWING_ANALYSIS_PIPELINE.md)).
- *"Never duplicated information"* — refined. Issued documents deliberately
  *freeze* copies of facts (a signed act must not change retroactively). The
  precise rule is: **no duplicated *live* state**; snapshots are immutable
  history (ADR-CS-002, [22_AUDIT_AND_VERSIONING.md](22_AUDIT_AND_VERSIONING.md)).
