# CS-06 — Non-Functional Requirements

Status: Draft · Date: 18.07.2026 · Inherits the Business OS baseline
(ServiceFlow docs/11 security model, docs/12 testing) — only module-specific
NFRs and deltas listed.

## 1. Correctness & determinism (the defining NFRs)

- **NFR-1** Generation determinism: same KB snapshot + same template version ⇒
  identical output bytes (modulo DOCX zip timestamps, which are normalized).
  This is a CI-tested property, not an aspiration.
- **NFR-2** No silent blanks: a generated legal field is either a confirmed
  fact or the generation fails with a finding. Placeholder leakage
  (`{{permit_no}}` in output) is a release-blocking defect class.
- **NFR-3** Fact integrity: no orphan facts (every fact belongs to a project),
  no dangling provenance (sources may be deleted only if no fact cites them —
  else soft-archive).
- **NFR-4** AI outputs are quarantined by construction: schema-invalid or
  unconfirmed proposals cannot reach the KB (enforced at the type/DB level,
  not by convention — ADR-CS-003).

## 2. Performance & capacity (sized to reality, pragmatism directive)

- Tens of projects, ~10 users per tenant; document generation < 5 s for any
  act; technical passport < 15 s.
- Extraction/OCR jobs are background work; interactive review must render a
  30-page PDF's proposals without pagination pain. No SLA on job latency in
  MVP beyond "visible progress".
- Storage: drawings dominate (100+ MB PDFs); storage port must stream, never
  buffer whole files in memory; per-tenant storage quota accounting is a
  platform question deferred to Core ([24 §4](24_INTEGRATION_WITH_BUSINESS_OS.md)).

## 3. Reliability & data safety

- Issued documents and their snapshots are immutable and backed up as
  first-class data (they are the firm's legal record). Restore drill covers
  KB + files + snapshots together (extends ServiceFlow docs/05 practice).
- A failed generation/extraction job leaves no partial state (transactional
  outbox for events; idempotent job retries — Core ADR-006 pattern).

## 4. Security & privacy

- All tables `company_id` + RLS FORCE, fail-closed (ADR-016); isolation P0.
- PII: participant registries hold names, addresses, diploma and register
  numbers — treated as PII: never logged (repo rule 7), export-controlled,
  GDPR subject-access answerable from the participant registry.
- AI calls send document content to the model provider: requires explicit
  tenant-level opt-in, a data-processing note, and redaction of ЕГН if ever
  present ([20_AI_STRATEGY.md §6](20_AI_STRATEGY.md)).

## 5. Auditability

- Every KB mutation, document issuance, finding transition: append-only audit
  with actor, timestamp — sufficient to answer "who put this number here and
  from what source" years later, offline, from an export
  ([22](22_AUDIT_AND_VERSIONING.md)).

## 6. Maintainability & evolvability

- New standard document type = registry data + template pair + rule set; no
  migration, no code (measured in [30 §AC-7](30_ACCEPTANCE_CRITERIA.md)).
- Regulatory change response (amended form) = new template/rule version with
  effective date; old documents keep their historical form.
- Module boundary enforced by import-linter from the first code PR — same CI
  discipline as ServiceFlow (BOS-04 rules R2/R3/R4).

## 7. Usability

- Bulgarian UI, terminology exactly matching the legal forms (glossary-driven).
- The review UI (accept/correct extraction proposals) is keyboard-first — it
  is the highest-frequency interaction for legacy imports.
- Findings phrased as actionable Bulgarian sentences with links to both sides
  of a conflict — engineers must not need to understand "rules" to fix data.
