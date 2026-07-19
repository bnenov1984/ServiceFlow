# CS-28 — Implementation Roadmap

Status: Draft · Date: 18.07.2026 · Interleaves with the Business OS roadmap
(BOS-08); ServiceFlow's delivery plan keeps priority — CS phases must not
destabilize Етап 2–4. Model column follows BOS convention (Fable 5 for
boundary/contract judgment, Sonnet for mechanical work against approved specs).

## Phase 0 — This documentation package ✅ (18.07.2026)

Exit: PO reviews CS-00…30 + ADR-CS-001…007; accepts/vetoes; confirms the
module commitment (which arms BOS Phase 3). Model: Fable 5.

## Pre-code gate — BOS Phase 3 (Core rename)

Not a CS phase, but its prerequisite (BOS-08: module #2 never imports
`serviceflow.*`). Scheduled between ServiceFlow stages; mechanical.
Model: Sonnet, Fable 5 reviews the boundary.

## Phase A — MVP: SSOT + generation loop ([27](27_MVP_DEFINITION.md))

Registry, parties/participations, KB core, four document types (Act 12/14/15,
Technical Passport) with template pairs, validation gate + core rules,
issuance/snapshots, timeline, isolation P0, bg UI.
Exit: sample project recreated end-to-end; pilot firm live on 1 project.
Risks: template fidelity (mitigate: golden renders vs real filled docs).
Model: Fable 5 for KB/taxonomy/template-manifest design; Sonnet for CRUD bulk.

## Phase B — Ingestion & the act chain

Deterministic parsers (DOCX/born-digital PDF), per-type extractors for the
known forms, combined-file splitting (актове-къща case), proposal review UI,
AI text extraction (opt-in, quarantined), conflict handling; document types
обр. 2/3/5/6/7/8/10/11 + 72h protocols; chronology + completeness rule
packs; Act 14/15 gates fully armed; proto-dossier → dossier view + Act 15
inventory auto-composition.
Exit: a legacy mid-stream project imported with < X min review per act
(baseline set in pilot); AI share and acceptance metrics live.
Model: Fable 5 for pipeline/quarantine seams; Sonnet for extractors.

## Phase C — Scans & drawings (reading)

OCR pipeline (Tesseract + escalation), page-image anchors in review UI,
drawing registry, title blocks, schedule table extraction (vector-first),
narrative composers for Act 15 parts (+ approved AI drafting).
Exit: scanned legacy dossier importable; drawing metadata feeding
consistency checks.
Model: Sonnet against specs; Fable 5 where extraction quality decisions bite.

## Phase D — Quantities

Structural elements, formula registry, three-way comparison
(computed/extracted/declared), tolerance findings; rebar schedules end-to-end.
Exit: the sample house's concrete/formwork/rebar figures reproduced from
inputs; comparisons flag seeded discrepancies.
Model: Fable 5 for the formula/units core; Sonnet for the rest.

## Phase E — Dossier & ecosystem

Dossier export bundle (ADR-012-aligned), batch generation, окончателен
доклад + дневник support, client read-only portal (decision point), КЕП
e-signature analysis → possible integration, ДПК/обр. 16 if a cat I–III
client exists.
Each item separately evidence-gated; none assumed.

## Cross-phase obligations

- Every phase updates: sample corpus, golden tests, rule fixtures, [24 §5](24_INTEGRATION_WITH_BUSINESS_OS.md)
  extraction watchlist, this roadmap's status lines.
- P0 (isolation, determinism, immutability) stays green throughout — any
  regression blocks release, same standing as repo rule 8.
- BOS Phase 6 (extraction of proven duplicates) is *not* on this roadmap —
  it belongs to Business OS governance once CS is in production.
