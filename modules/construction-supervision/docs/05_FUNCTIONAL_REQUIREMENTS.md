# CS-05 — Functional Requirements

Status: Draft · Date: 18.07.2026 · Requirement ids are stable (`FR-x.y`);
MVP column refers to [27_MVP_DEFINITION.md](27_MVP_DEFINITION.md) phases in
[28_IMPLEMENTATION_ROADMAP.md](28_IMPLEMENTATION_ROADMAP.md).

## 1. Project Registry

| ID | Requirement | Phase |
|---|---|---|
| FR-1.1 | Create/edit a construction project: name, category (+ legal basis), cadastral identifiers, address/location, status. | MVP |
| FR-1.2 | Record the building permit: number, date, issuer, approved project parts, approval dates; amendments (преработки) as dated revisions. | MVP |
| FR-1.3 | Multiple cadastral identifiers per project (ПИ, сграда, съоръжение) with explicit kinds — never a free-text blob. | MVP |
| FR-1.4 | Project lifecycle status derived from workflow state (никога ръчно поле that can contradict the documents). | MVP |

## 2. Participants

| ID | Requirement | Phase |
|---|---|---|
| FR-2.1 | Firm-level participant library: persons and companies with typed credentials (ЕИК, ДНСК удостоверение + validity, КИИП/КАБ рег. №, дипломи, ЦПРС) — reusable across projects. | MVP |
| FR-2.2 | Project participation: role (възложител, строител, проектант по част, надзор по част, техн. ръководител…), part, time bounds, appointing document (договор, заповед). | MVP |
| FR-2.3 | Mid-project participant change (e.g. builder replacement) representable without losing history; documents reference the participation valid at their date. | MVP |
| FR-2.4 | Credential validity warnings (удостоверение expiring/expired at act date) as rule findings. | B |

## 3. Knowledge Base

| ID | Requirement | Phase |
|---|---|---|
| FR-3.1 | Every project fact stored once, typed (text, date, number+unit, identifier, enum, reference), with provenance per [21](21_PROVENANCE_AND_CONFIDENCE.md). | MVP |
| FR-3.2 | Fact edit = new version with author, timestamp, reason; full history retained. | MVP |
| FR-3.3 | Facts referenced by documents at generation time; issued documents keep a frozen snapshot. | MVP |
| FR-3.4 | Show, for any fact, every document that displays it (impact view) and every source that evidences it. | B |

## 4. Document Repository (sources)

| ID | Requirement | Phase |
|---|---|---|
| FR-4.1 | Upload PDF/DOCX/images; stored via Core storage port; classified by document type (manual in MVP, assisted later). | MVP |
| FR-4.2 | A combined multi-act file can be split into per-act source registrations (the актове-къща case) — split points user-confirmed. | B |
| FR-4.3 | Source pages addressable (doc id + page) so provenance can point into them. | B |

## 5. Extraction (pipelines detailed in [16](16_DOCUMENT_EXTRACTION_PIPELINE.md))

| ID | Requirement | Phase |
|---|---|---|
| FR-5.1 | Deterministic text extraction from born-digital PDF/DOCX. | B |
| FR-5.2 | AI extraction produces schema-constrained proposals with confidence and source anchors; never writes facts directly. | B |
| FR-5.3 | Review UI: side-by-side source and proposals; accept/correct/reject each; acceptance creates facts with provenance. | B |
| FR-5.4 | OCR for scans, same proposal flow. | C |
| FR-5.5 | Extraction from drawings: title blocks, schedule tables ([17](17_DRAWING_ANALYSIS_PIPELINE.md)). | C/D |

## 6. Quantities ([18](18_QUANTITY_CALCULATION_ENGINE.md))

| ID | Requirement | Phase |
|---|---|---|
| FR-6.1 | Structural element registry (foundations, columns, walls/шайби, beams, slabs, roof) with dimensions per level. | D |
| FR-6.2 | Deterministic concrete/formwork/reinforcement quantity computation with declared formulas and rounding. | D |
| FR-6.3 | Comparison of computed vs. extracted vs. act-declared quantities with tolerance rules → findings. | D |

## 7. Templates & Generation ([12](12_TEMPLATE_ENGINE.md), [15](15_DOCUMENT_GENERATION_PIPELINE.md))

| ID | Requirement | Phase |
|---|---|---|
| FR-7.1 | Versioned template pairs: visual .docx + machine manifest (bindings, conditions, loops, calculations, required-field rules). | MVP |
| FR-7.2 | Generate DOCX for: **Act 12, Act 14, Act 15, Technical Passport** — each its own document type (ADR-CS-005). | MVP |
| FR-7.3 | Generation is deterministic and repeatable; a draft can be regenerated any number of times until issuance. | MVP |
| FR-7.4 | Validation gate: generation refuses (with findings list) if required facts are missing/invalid — no silently blank legal fields. | MVP |
| FR-7.5 | Issuance freezes the document: data snapshot, number, date; issued docs immutable (new version requires formal supersede). | MVP |
| FR-7.6 | Additional types (обр. 2–8, 10, 11, test protocols, окончателен доклад, обр. 16) added as registry data + templates, no code change for standard cases. | B+ |
| FR-7.7 | Narrative sections (Act 15 per-part descriptions) assembled from structured inputs; optional AI drafting, always human-approved before entering the document. | C |

## 8. Rules & Consistency ([13](13_RULES_ENGINE.md), [19](19_VALIDATION_AND_CONSISTENCY.md))

| ID | Requirement | Phase |
|---|---|---|
| FR-8.1 | Field/document-level validation rules per document type (required, format, value domain). | MVP |
| FR-8.2 | Cross-document consistency: same project name, identifiers, permit, participants across all documents; mismatches → findings. | MVP (core set) |
| FR-8.3 | Chronology rules: act dates ordered per lifecycle; e.g. обр. 8 ≥ pour date + curing period; обр. 14 after all structural обр. 7/12. | B |
| FR-8.4 | Completeness rules per category/phase: what must exist before a gate (Act 15 inventory completeness). | B |
| FR-8.5 | Findings have severity (blocker/warning/info), status (open/acknowledged/resolved/waived+reason), and audit. | MVP |

## 9. Workflow & Timeline ([14](14_WORKFLOW_ENGINE.md))

| ID | Requirement | Phase |
|---|---|---|
| FR-9.1 | Per-document-type state machine: draft → ready → prepared → issued (→ superseded); transitions via a single endpoint (mirrors BR-4 discipline). | MVP |
| FR-9.2 | Project phases (подготовка, изкопни, груб строеж, довършителни, изпитания, приемане, въведен) derived from issued documents. | B |
| FR-9.3 | Phase gates: configurable required-document checks blocking phase-advancing documents (Act 14 gate, Act 15 gate). | B |
| FR-9.4 | Append-only project timeline of every significant event (fact confirmed, doc issued, finding raised/resolved). | MVP |

## 10. Dossier & Audit ([22](22_AUDIT_AND_VERSIONING.md))

| ID | Requirement | Phase |
|---|---|---|
| FR-10.1 | Dossier view: ordered inventory of all documents (generated + sources) with status; export as structured index + files. | B |
| FR-10.2 | Act 15's document inventory section auto-composed from the dossier. | B |
| FR-10.3 | Full audit: every fact/document/finding change attributable (who/when/what/why). | MVP |

## 11. Cross-cutting

| ID | Requirement | Phase |
|---|---|---|
| FR-11.1 | Multi-tenant: all data company-scoped under Business OS RLS (ADR-016); tenant isolation P0 tests. | MVP |
| FR-11.2 | UI Bulgarian via bg catalog; backend returns message keys (ADR-015). | MVP |
| FR-11.3 | Long-running pipeline steps (OCR, AI extraction) run as background jobs with visible status (Core job pattern, ADR-006). | B |
