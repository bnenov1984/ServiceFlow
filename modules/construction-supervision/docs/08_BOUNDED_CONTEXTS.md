# CS-08 — Bounded Contexts

Status: Draft · Date: 18.07.2026

Seven contexts inside one module (one deployable, one schema — ADR-BOS-001).
"Context" here means: own ubiquitous language, own tables, interactions via
application services/events — the same internal discipline ServiceFlow uses
between its domain packages, enforceable later by import-linter at the
package level.

## 1. Context map

```
                    ┌────────────────────┐
                    │  Project Registry   │  projects, permits, parties,
                    │  (упр. на обекти)   │  participations
                    └───┬────────────┬───┘
            identity of  │            │ participants for
            everything   ▼            ▼
┌──────────────────┐   ┌──────────────────────┐   ┌───────────────────────┐
│ Ingestion &      │──▶│   Knowledge Base      │◀──│ Drawings & Quantities │
│ Extraction       │   │  (facts+provenance)  │   │ (elements, calc)      │
│ sources, OCR, AI │   └───┬──────────────┬───┘   └──────────┬────────────┘
└──────────────────┘       │              │                  │
   proposals only ▲        ▼              ▼                  ▼ quantity claims
                  │  ┌───────────────┐  ┌──────────────────────┐
                  └──│  Compliance    │  │ Document Production  │
                     │ rules,findings │◀─│ types,templates,gen  │
                     └───────┬────────┘  └──────────┬───────────┘
                             ▼                      ▼
                     ┌──────────────────────────────────┐
                     │      Dossier & Timeline           │
                     │ workflow state, audit, export     │
                     └──────────────────────────────────┘
```

## 2. Context charters

| Context | Owns | Never does |
|---|---|---|
| **Project Registry** | projects, permits, cadastral ids, parties, participations | store per-document copies of its data |
| **Ingestion & Extraction** | source documents/pages/sections, extraction batches & proposals, OCR artifacts | write confirmed facts (only proposals) |
| **Knowledge Base** | facts, fact versions, provenance, fact taxonomy | render documents; call AI |
| **Drawings & Quantities** | drawings/sheets, structural elements, quantity computations | declare quantities "correct" (that's Compliance's comparison) |
| **Document Production** | document-type registry, template versions+manifests, generated documents, snapshots, issuance | mutate facts; bypass the validation gate |
| **Compliance** | rules, rule sets, findings | block anything itself — it reports; gates consume findings |
| **Dossier & Timeline** | workflow definitions/states, phase gates, timeline projection, dossier index/export, domain audit | own business data (pure projection + state machines) |

## 3. Key relationships (translation, not shared models)

- Extraction → KB: **proposal/acceptance protocol** (the module's most
  important seam; the AI quarantine line runs exactly here — ADR-CS-003).
- KB → Document Production: **read-only fact resolution** by path at
  generation; snapshot on issuance.
- Registry → everything: ids only; consumers hold references, not copies.
- Compliance reads all, writes only findings; Production's validation gate
  asks Compliance "blockers for type X now?".
- Dossier subscribes to events from all contexts (ADR-011 in-process bus).

## 4. Why not fewer contexts?

Merging Extraction into KB would blur the single most safety-critical rule
(what is proposed vs. confirmed). Merging Production into Compliance couples
rendering to rule evolution — template versioning and rule versioning move on
different clocks (regulatory amendments vs. layout fixes). The others earn
separation by having genuinely different change drivers. Fewer than these
seven and the module re-creates the copy-paste ambiguity it exists to kill;
more (e.g. separate "Workflow" from "Dossier") is ceremony without a second
change driver — resisted per the pragmatism directive.
