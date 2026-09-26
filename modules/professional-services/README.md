# Professional Services (Професионални услуги)

**Business OS vertical module #3** — operational control for small Bulgarian
professional-service firms: construction supervisors, valuers, court experts,
engineers, architects, surveyors, accountants, legal/administrative service
providers. Status: **Implemented** (status corrected 20.09.2026 — this line
still read "Phase 0 … no application code exists yet", which
[docs/INDEX.md](../../docs/INDEX.md) has contradicted for some time). The
module ships as `backend/src/professional_services/` (assignments, clients,
catalog, actions), migrations `0007_professional_services`,
`0010_ps_workflow`, `0011_ps_deadline_engine`, the `test_ps_*.py` suites, and
the PropertyFlow frontend under `frontend/src/ps/`. The documents below remain
the product/architecture reference for it; where a doc and the code disagree,
the code is current.

Module identifier: `professional-services` (future Python package:
`professional_services`; table prefix `ps_`; i18n namespace `ps.`).

## What this is

Small professional firms live from **assignments**: a client calls, an
engagement is accepted, work happens, a deliverable goes out — usually against
an official deadline. Today those assignments live in notebooks, Excel, email
threads, and human memory. The consequences are missed deadlines, forgotten
cases, unclear ownership, and clients who must call to ask "докъде сме?".

This module gives such a firm one operational surface that always answers:
*what work exists, who owns it, what stage it is in, what happens next, when
it is due, what documents are missing, and what is silently going stale.* Its
two load-bearing concepts are the **Next Action** (every active assignment
says what must happen next, by whom, by when) and the **deterministic deadline
& inactivity engine** (risk states computed from data, reproducible, never
AI-driven).

This is **not** a rename of ServiceFlow. ServiceFlow's aggregate is a repair
of a physical asset; this module's aggregate is an **Assignment** — work
accepted from a client with deadlines, a document dossier, and a configurable
workflow. See [docs/27_SERVICEFLOW_REUSE_AUDIT.md](docs/27_SERVICEFLOW_REUSE_AUDIT.md)
for the capability-by-capability reuse verdicts.

## Reading order

| Start here | Then |
|---|---|
| [docs/00_PRODUCT_VISION.md](docs/00_PRODUCT_VISION.md) | vision and differentiators |
| [docs/02_SCOPE_AND_GUARDRAILS.md](docs/02_SCOPE_AND_GUARDRAILS.md) | what we will NOT build |
| [docs/09_DOMAIN_MODEL.md](docs/09_DOMAIN_MODEL.md) | the Assignment aggregate |
| [docs/12_WORKFLOW_AND_STATUS_MODEL.md](docs/12_WORKFLOW_AND_STATUS_MODEL.md) | lifecycle states vs configurable stages |
| [docs/13_DEADLINE_AND_REMINDER_ENGINE.md](docs/13_DEADLINE_AND_REMINDER_ENGINE.md) | the deadline/risk engine |
| [docs/27_SERVICEFLOW_REUSE_AUDIT.md](docs/27_SERVICEFLOW_REUSE_AUDIT.md) | reuse verdicts vs ServiceFlow / Core |
| [docs/34_MVP_DEFINITION.md](docs/34_MVP_DEFINITION.md) | what ships first |
| [docs/adr/](docs/adr/) | architecture decisions (none frozen yet) |

Numbering is module-local (00–38); it intentionally follows the structure this
module was commissioned with and does not have to match
`construction-supervision`'s internal numbering.

## Directory layout

```
modules/professional-services/
├── README.md          this file
├── docs/              39 numbered documents + adr/
├── schemas/           draft JSON Schemas (assignments, workflows, deadlines,
│                      notifications, integrations)
└── examples/          three worked domain examples: court-expertise,
                       real-estate-valuation, construction-acts
```

## Relationship to Business OS

- Governed by the platform documents ([docs/business-os/](../../docs/business-os/00_VISION_AND_SCOPE.md)),
  the pragmatism directive (repo CLAUDE.md rule 1), and tenant isolation
  (ADR-016).
- Reuses **Core only through its public contracts**: identity/tenancy
  (`identity.deps` / `identity.contracts` per BOS-16), `shared_kernel`
  primitives (UUIDv7 ids, storage port, event bus, normalization), the i18n
  mechanism (ADR-015), and platform services as they land in Етап 3.
- Where this module wants something ServiceFlow has (tasks, attachments,
  contacts, timeline), it **builds its own or waits** (BOS-08 Phase 5 rule).
  Extraction into shared platform code happens only later, from two concrete
  implementations (BOS-08 Phase 6). See ADR-PS-002.
- Never imports `serviceflow` domain modules; never touches their tables
  (BOS-04/BOS-05 rules, enforced by import-linter when code exists).
- Integration with the Construction Documentation module
  (`construction-supervision`) is by explicit link + contract, not by merging
  contexts — see [docs/29_CONSTRUCTION_DOCUMENTATION_INTEGRATION.md](docs/29_CONSTRUCTION_DOCUMENTATION_INTEGRATION.md).

## Language policy

Docs and code in English; UI and all user-facing copy in Bulgarian (bg
catalog, ADR-015 mechanism). Domain terms are bilingual in
[docs/04_GLOSSARY_AND_TERMINOLOGY.md](docs/04_GLOSSARY_AND_TERMINOLOGY.md).
The visible name of the core object is configurable per organisation
(Поръчка / Възлагане / Досие / Преписка / …); the internal term is always
`Assignment` (ADR-PS-004).
