# CS-09 — System Architecture

Status: Draft · Date: 18.07.2026 · Companion: [24_INTEGRATION_WITH_BUSINESS_OS.md](24_INTEGRATION_WITH_BUSINESS_OS.md),
[25_TECHNOLOGY_STACK.md](25_TECHNOLOGY_STACK.md), [26_REPOSITORY_STRUCTURE.md](26_REPOSITORY_STRUCTURE.md).

## 1. Placement: a module in the Business OS modular monolith

One deployment, one PostgreSQL database, one FastAPI application
(ADR-BOS-001). `construction_supervision` is a vertical package parallel to
ServiceFlow's domain packages, importing **Core only** (identity via
`identity.deps`/`identity.contracts`, `shared_kernel`, platform services) and
**never** any `serviceflow` domain module — enforced by import-linter from
the first code PR.

```
┌──────────────────────────── Business OS app ───────────────────────────┐
│  Core: identity · tenancy/RLS · shared_kernel (ids, db, events,        │
│        storage port, i18n mechanism) · platform (health, jobs, config) │
├───────────────────────────┬────────────────────────────────────────────┤
│  serviceflow.* (module 1) │  construction_supervision (module 2)       │
│  service orders, …        │  registry · kb · ingestion · drawings ·    │
│                           │  production · compliance · dossier        │
└───────────────────────────┴────────────────────────────────────────────┘
```

## 2. Internal layering (per context, same discipline as ServiceFlow)

router (HTTP, thin) → application service (use cases, transactions) →
domain (entities, invariants, pure logic) → adapters (DB repositories,
storage, DOCX renderer, AI client). Domain layer imports nothing above it;
AI/OCR clients live strictly in adapters so the domain is testable offline.

## 3. The two macro-flows

### 3.1 Inbound (documents → knowledge)

```
upload ──▶ SourceDocument (storage port, hashed, virus-scan hook)
   └─▶ classify (manual MVP / model-assisted later)
   └─▶ [job] deterministic parse: born-digital text, tables, title blocks
   └─▶ [job] OCR when scanned (phase C)
   └─▶ [job] AI extraction → schema-validated proposals (confidence, anchors)
   └─▶ human review UI → accept/correct/reject
   └─▶ KB: confirmed facts + provenance  ──▶ events ──▶ findings recompute
```

### 3.2 Outbound (knowledge → documents)

```
choose document type + instance context (e.g. обр.12 "армировка основи")
   └─▶ resolve bindings against KB (confirmed facts only)
   └─▶ validation gate: rule set for type ⇒ blockers? stop with findings
   └─▶ deterministic render: manifest + .docx template version → DOCX draft
   └─▶ (iterate: fix facts, regenerate)
   └─▶ issue: DataSnapshot + number/date + file hash → immutable version
   └─▶ events ──▶ timeline, dossier index, phase gates
```

No AI anywhere in 3.2 (ADR-CS-003). Long steps in 3.1 are background jobs
using the Core DB-backed job pattern (ADR-006) — no new queue infrastructure
until job volume proves otherwise (pragmatism directive).

## 4. Consistency engine placement

Findings recompute is event-driven and incremental: a changed fact triggers
re-evaluation of rules subscribed to its path (rule→path index), not a
project-wide sweep; a nightly full sweep backstops drift. Both run in-process
as jobs. Detailed design: [13_RULES_ENGINE.md](13_RULES_ENGINE.md),
[19_VALIDATION_AND_CONSISTENCY.md](19_VALIDATION_AND_CONSISTENCY.md).

## 5. Storage architecture

- **PostgreSQL** — all structured data, RLS-scoped per ADR-016; JSONB for
  manifest documents, snapshots, proposal payloads (typed at the edges by
  Pydantic models + JSON Schemas in [schemas/](../schemas/README.md)).
- **File storage via Core storage port (ADR-007)** — sources, drawings,
  rendered DOCX; content-addressed (sha256) so snapshots can prove which
  bytes were issued. Local filesystem/S3 per deployment, invisible to domain.

## 6. Frontend

React SPA area within the Business OS frontend shell, own feature folder
tree, bg catalog namespace `cs.*`. The frontend boundary rule (BOS Phase 2's
R9-lite) applies: shared `lib/components` never import from feature folders.
Heavy views: review UI (source page + proposal list), findings board, dossier
tree, generation preview. No PDF/DOCX rendering client-side beyond preview
links in MVP.

## 7. Deliberate non-choices (challenged alternatives)

- **No microservice for "AI pipeline"** — a Python package + jobs suffices at
  this scale; a service boundary would only add failure modes (reaffirms
  ADR-BOS-001).
- **No workflow-engine dependency (Camunda/Temporal)** — the state machines
  are small, finite, and legally fixed; code + registry data beats an engine
  (see [14 §5](14_WORKFLOW_ENGINE.md)).
- **No vector DB / RAG layer** — extraction is schema-constrained reading of
  known document kinds, not open-ended retrieval ([20 §7](20_AI_STRATEGY.md)).
- **No shared "document platform" with ServiceFlow yet** — BOS Phase 6 owns
  that decision after two implementations exist ([24 §5](24_INTEGRATION_WITH_BUSINESS_OS.md)).
