# Construction Supervision (Строителен надзор)

**Business OS vertical module #2** — a structured-knowledge-base platform for
Bulgarian construction supervision companies (консултанти, упражняващи
строителен надзор по чл. 166 ЗУТ). Status: **Phase 0 — architecture &
documentation. No application code exists yet.**

Module identifier: `construction-supervision` (future Python package:
`construction_supervision`).

## What this is

Construction supervision firms produce dozens of highly repetitive documents
per project (Наредба №3/2003 acts, technical passports, protocols). Today the
same facts — project name, cadastral identifier, permit number, participants —
are re-typed into every document, and they drift. This module inverts the
model: **the project exists once, as a structured knowledge base; every
document is a generated view over it.** Deterministic core, AI only at the
edges (extraction proposals, never authoritative writes).

This is **not** a chatbot and **not** a standalone application. It is a
first-class module of Business OS, parallel to ServiceFlow, reusing Core
(tenancy, identity, RLS isolation, ids, storage, events, i18n mechanism) and
owning everything vertical (acts, templates, rules, workflow, extraction).

## Reading order

| Start here | Then |
|---|---|
| [docs/00_PRODUCT_VISION.md](docs/00_PRODUCT_VISION.md) | vision, SSOT philosophy |
| [docs/01_SCOPE_AND_GUARDRAILS.md](docs/01_SCOPE_AND_GUARDRAILS.md) | what we will NOT build |
| [docs/02_DOMAIN_KNOWLEDGE_BIBLE.md](docs/02_DOMAIN_KNOWLEDGE_BIBLE.md) | the regulatory & practice domain |
| [docs/24_INTEGRATION_WITH_BUSINESS_OS.md](docs/24_INTEGRATION_WITH_BUSINESS_OS.md) | boundary with Core — governing doc |
| [docs/27_MVP_DEFINITION.md](docs/27_MVP_DEFINITION.md) | what ships first |
| [docs/adr/](docs/adr/) | binding architecture decisions |

Full index: docs/00–30 follow a fixed numbering; each file states its own
status (Draft / Proposed / Accepted).

## Directory layout

```
modules/construction-supervision/
├── README.md            this file
├── docs/                31 numbered architecture documents + adr/
├── samples/             real-world source documents & expected outputs (see samples/README.md)
└── schemas/             draft JSON Schemas for core artifacts (see schemas/README.md)
```

## Sibling modules

This module is independent of ServiceFlow (vertical #1) **and** of
[Professional Services](../professional-services/README.md) (vertical #3,
engagement/assignment management). The division of responsibility with
Professional Services — CS owns construction content (acts, passports,
templates, validation, generation); PS owns the client-engagement wrapper
(assignments, deadlines, next actions) — is recorded in PS's
[29_CONSTRUCTION_DOCUMENTATION_INTEGRATION.md](../professional-services/docs/29_CONSTRUCTION_DOCUMENTATION_INTEGRATION.md).

## Relationship to Business OS

- Governed by the Business OS platform documents
  ([docs/business-os/](../../docs/business-os/00_VISION_AND_SCOPE.md)) and the
  pragmatism directive (repo CLAUDE.md rule 1).
- This module's commitment is the **trigger** for BOS roadmap Phase 3 (Core
  package rename) and Phase 5 (second real module) — see
  [ADR-CS-001](docs/adr/ADR-CS-001-business-os-vertical-module.md).
- Where this module wants something ServiceFlow has, it **builds its own or
  waits** (BOS-08 Phase 5 rule); extraction into shared platform happens only
  from two concrete implementations (BOS-08 Phase 6).

## Language policy

Docs and code in English; UI, templates, and all generated documents in
Bulgarian (bg catalog, ADR-015 mechanism). Domain terms are kept bilingual in
[docs/03_GLOSSARY.md](docs/03_GLOSSARY.md).
