# CS-26 — Repository Structure

Status: Draft · Date: 18.07.2026 · Describes (a) what exists now, (b) the
planned code layout when implementation starts (post BOS Phase 3 rename).

## 1. Now (documentation phase)

```
<repo root>                        # the Business OS repository
├── backend/  frontend/  docs/     # existing (ServiceFlow + Core + BOS docs)
└── modules/
    └── construction-supervision/  # THIS module's product definition
        ├── README.md
        ├── docs/                  # CS-00…CS-30 + adr/ADR-CS-*
        ├── samples/               # source-documents / annotated-documents /
        │                          # template-examples / expected-outputs
        └── schemas/               # project / documents / templates /
                                   # workflows / extraction  (draft JSON Schemas)
```

`modules/` is a *documentation* home today. Whether future modules' docs all
live under `modules/<name>/docs` or consolidate into the top-level `docs/`
tree is a PO layout decision to make at Phase-3 time — nothing here blocks
either (risk noted in ADR-CS-001 §Consequences).

## 2. Planned backend package (first code PR, after BOS Phase 3 rename)

```
backend/src/
├── business_os/                   # Core after Phase 3 (identity, shared_kernel, platform)
├── serviceflow/                   # vertical #1 (unchanged)
└── construction_supervision/      # vertical #2 — one package per bounded context
    ├── registry/        # projects, permits, parties, participations
    │   ├── models.py  service.py  router.py  schemas.py
    ├── knowledge/       # facts, versions, provenance, taxonomy
    ├── ingestion/       # sources, sections, extraction batches/proposals
    │   └── adapters/    # parsers (docx, pdf), ocr, ai clients  ← AI lives ONLY here
    ├── drawings/        # drawings, sheets, elements, quantities (phase C/D)
    ├── production/      # document types, templates, generation, issuance
    │   └── adapters/    # docx renderer, pdf preview
    ├── compliance/      # rules, findings
    ├── dossier/         # workflow defs, transitions, timeline, export
    ├── contracts.py     # EMPTY in v1 (no external consumers — BOS-04)
    ├── catalog_bg.py    # module i18n keys (cs.*)
    └── migrations/      # module-owned alembic revisions (cs_* tables)
```

Import rules (added to `backend/.importlinter` in the same PR that creates
the package):
- `construction_supervision` may import `business_os.*` only — never
  `serviceflow.*` (and vice versa).
- Core never imports `construction_supervision` (existing R3 becomes
  structural).
- Within the module: `*/adapters` may not be imported by `knowledge`
  (the AI-quarantine import rule — [16 §3](16_DOCUMENT_EXTRACTION_PIPELINE.md));
  contexts communicate via services, not each other's models (start as
  convention + architecture test, ratchet like BOS Phase 1 did).

## 3. Planned frontend area

```
frontend/src/features/cs/          # feature folders per context surface
    projects/  participants/  sources/  review/   # review = proposal UI
    documents/ findings/ dossier/
frontend/src/i18n/bg.ts            # + cs.* namespace (single catalog file
                                   #   or per-module split — follow the
                                   #   frontend's standing pattern at code time)
```

Frontend boundary tests (Phase 2's vitest mechanism) extend to `cs/`
features.

## 4. Tests

```
backend/tests/construction_supervision/
    test_tenancy_p0.py             # isolation tests from migration #1
    test_generation_golden.py      # byte-stable renders per template version
    test_rules_fixtures.py         # the sample-defect regression trio
    test_architecture.py           # module import rules
    fixtures/                      # anonymized sample-derived data
```
