# CS-27 — MVP Definition

Status: **Draft for PO review** · Date: 18.07.2026

## 1. MVP thesis

The smallest thing a supervision firm would pay for is **not** OCR and not
drawing AI — it is: *enter the project once, generate the recurring documents
correctly, and never let them disagree.* The MVP is the SSOT + generation
loop for one real project class: **category V single-family house** (the
sample project, start to finish).

## 2. MVP scope (maps to roadmap Phase A)

**In:**
1. Project registry: project, category, cadastral ids, permit (+amendments).
2. Party library + project participations (roles, parts, validity, the
   builder-change case).
3. Knowledge base for the passport/long-tail facts, with versions and manual
   provenance; confirmed-only generation inputs.
4. Document types + templates + generation for:
   **Act 12** (instance family), **Act 14**, **Act 15**,
   **Technical Passport** — the brief's target four, each fully independent
   (ADR-CS-005).
5. Validation gate + core rule set: required fields, formats, cross-document
   equality on the header block, credential validity, basic chronology
   (act ordering), findings board with waivers.
6. Document lifecycle: draft → ready → prepared → issued (snapshot,
   immutable), supersede; per-project document list (proto-dossier).
7. Source upload + manual classification (files attach as evidence; no
   parsing yet).
8. Timeline; domain audit; tenant isolation P0; bg UI.

**Out (explicitly), with their phase:** extraction/OCR (B/C), combined-file
splitting (B), обр. 2–8/10/11 generation (B), drawings (C), quantities (D),
AI anything (B+), dossier export (E), client portal (E), e-signature (E),
ДПК/обр. 16 (later, evidence-gated).

## 3. MVP acceptance (detail in [30](30_ACCEPTANCE_CRITERIA.md))

- Recreate the sample project end-to-end: all four document types generated
  with **zero re-typed facts** across them; outputs field-equivalent to the
  firm's real filled documents.
- The three sample defect classes are impossible-or-flagged: identifier
  drift (structurally prevented in generated docs; flagged on entry),
  wrong-form boilerplate (impossible — types own templates), chronology
  errors (flagged).
- Issued documents immutable; every fact's history inspectable.
- Isolation P0 green; generation deterministic in CI.

## 4. MVP non-goals worth stating loudly

- No claim of legal advice: the firm remains the author; the system prepares.
- No automatic data entry: MVP data is typed in by the firm (fast, because
  each fact is typed once). This keeps MVP free of the entire AI/extraction
  risk surface while delivering the core value; extraction then has a
  measurable baseline to beat (time-to-dossier with vs without).

## 5. Pilot shape

One friendly firm (the sample provider), 1–2 live projects, MVP in
parallel with their current Word practice; success = they stop opening the
old templates for those projects. Their existing templates are the golden
sources; their feedback drives phase B ordering.
