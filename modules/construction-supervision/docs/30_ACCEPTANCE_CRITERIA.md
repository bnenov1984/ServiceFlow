# CS-30 — Acceptance Criteria

Status: Draft · Date: 18.07.2026 · Criteria are testable; each maps to CI
tests or pilot checks. MVP = Phase A unless marked.

## AC-1 — Single source of truth

- [ ] Recreating the sample project, every shared fact (project name,
      category, cadastral ids, permit, each participant + credentials) is
      entered **exactly once** and appears correctly in all four generated
      document types.
- [ ] Changing `permit.number` once updates every *draft* document on next
      generation; **no** issued document changes (snapshot proof).
- [ ] No table in the module schema stores a second writable copy of a live
      fact (schema review + architecture test).

## AC-2 — Generation

- [ ] Act 12, Act 14, Act 15, Technical Passport generate to DOCX
      field-equivalent with the firm's real filled samples given the same
      data (golden fixtures, human-verified once, then CI-locked).
- [ ] Same inputs + same template version ⇒ identical bytes (normalized) —
      CI determinism test.
- [ ] Generation with a missing hard-required fact **fails** with a bg
      message-keyed finding; no output file is produced.
- [ ] No placeholder token ever appears in output (scan test on goldens).
- [ ] Act 14 is produced by its **own** template/manifest/rule set/workflow —
      demonstrably independent of Act 12/15 artifacts (registry inspection
      test; ADR-CS-005).

## AC-3 — Immutability & audit

- [ ] Issued version rows reject UPDATE (trigger test); supersede requires
      reason and produces a field-level diff view.
- [ ] For any generated value in an issued document, the UI (and the export)
      can show: fact version, author, timestamp, provenance chain.
- [ ] Every state transition appears in the transitions log with actor.

## AC-4 — Consistency engine (sample-defect regression trio)

- [ ] The anonymized passport fixture with two cadastral identifiers ⇒
      `cross_doc_equal` blocker finding naming both values and locations.
- [ ] The обр.7-header/обр.12-body fixture ⇒ `cross_ref_match` finding.
- [ ] The 2021 protocol with 2020 table dates (and the malformed
      "20.04.12.2021") ⇒ chronology/format findings.
- [ ] Waiving a warning requires a reason; the waiver survives re-evaluation
      and auto-reopens if underlying values change.

## AC-5 — Workflow gates (Phase B)

- [ ] Act 14 issuance is refused while a structural обр. 12 chain is open,
      with the specific missing items listed.
- [ ] Act 15's document inventory section auto-lists every issued document
      and flags dossier gaps.
- [ ] обр. 10/11 suspension window causes date-inside-suspension findings.

## AC-6 — Extraction (Phase B/C)

- [ ] The nine обр. 12 instances in the combined sample parse
      **deterministically** (zero AI calls): header block, date, scope,
      works tables — ≥ target field recall (set with pilot, fixture-locked).
- [ ] Splitting актове-къща.docx produces per-act source sections each
      mapped to the right type.
- [ ] No path exists from AI adapters to KB writes (import-linter contract
      + DB constraint tests).
- [ ] An extracted value conflicting with a confirmed fact produces a
      conflict proposal, never an overwrite.

## AC-7 — Registry extensibility

- [ ] Adding обр. 6 as a new document type (registry row + template pair +
      rule set) requires **zero code changes** — demonstrated in a test that
      registers a type at runtime and generates from it.

## AC-8 — Platform obligations

- [ ] Tenant isolation P0 tests for all `cs_*` tables and stored files pass
      (two-tenant fixture).
- [ ] Import-linter: module imports Core only; Core and `serviceflow.*`
      unaffected; ServiceFlow's full suite stays green with the module
      installed (the BOS-00 §9 platform proof).
- [ ] All UI strings from the bg catalog; backend returns message keys only.
- [ ] No PII in logs (log-scan test on pipeline runs).
