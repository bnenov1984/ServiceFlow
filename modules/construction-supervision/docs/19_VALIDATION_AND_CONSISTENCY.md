# CS-19 — Validation and Consistency

Status: Draft · Date: 18.07.2026 · The layered application of the rules
engine ([13](13_RULES_ENGINE.md)) across the system's surfaces.

## 1. Validation layers (defense in depth)

| Layer | When | What | Failure mode |
|---|---|---|---|
| L1 Schema | API boundary | types, enums, shapes (Pydantic + JSON Schemas) | 422, message keys |
| L2 Field | fact write / proposal accept | format rules: dates, ЕИК checksum, cadastral shape, unit vocabulary | rejected write with reason |
| L3 Entity | domain invariants | participation windows don't overlap per role; permit chain ordered; unique identifiers per kind | domain error |
| L4 Document | generation stage 3 | required bindings present & confirmed; type-specific rules | generation refused, findings list |
| L5 Cross-document | event-driven + sweep | equality across documents, chronology, credential validity, quantity tolerances | findings (blocker/warning/info) |
| L6 Project/gate | transition attempts | completeness per phase gate, open blockers | transition refused with the findings |

L1–L3 are *hard* (bad data cannot enter). L4–L6 are *advisory-until-gated*
(real projects carry documented imperfections; the system records and warns —
waivers with reasons, [13 §4](13_RULES_ENGINE.md)).

## 2. The consistency engine's target catalog

Mapped one-to-one from the brief + observed defects ([02 §7](02_DOMAIN_KNOWLEDGE_BIBLE.md)):

| Brief item | Mechanism |
|---|---|
| Different project names | `cross_doc_equal(identification.name)` — normalized compare (quotes/spacing vary legitimately in the samples) with strict option |
| Different addresses | `cross_doc_equal(identification.address+location)` |
| Different permit numbers | `cross_doc_equal(permit.number/date/issuer)` |
| Participant mismatches | participation-vs-document diff: signatory list on each doc vs participations valid at doc date (catches builder-change leakage) |
| Drawing inconsistencies | drawing title-block facts vs project facts; revision supersession checks ([17 §3](17_DRAWING_ANALYSIS_PIPELINE.md)) |
| Quantity mismatches | three-way tolerance comparison ([18 §3](18_QUANTITY_CALCULATION_ENGINE.md)) |
| Missing certificates | completeness: materials referenced in acts (concrete class, steel class) each need a matching declaration/certificate ingested |
| Missing documents | gate completeness sets per category ([14 §2](14_WORKFLOW_ENGINE.md)) |
| Invalid chronology | chronology kind: full ordering graph of the act chain + in-document date coherence |
| Conflicting information | conflict proposals at ingestion ([16 §5](16_DOCUMENT_EXTRACTION_PIPELINE.md)) + `cross_doc_equal` on live data |

## 3. Where consistency is *structural* (better than checking)

The strongest consistency mechanism is the SSOT itself: documents generated
from one KB **cannot** disagree on shared facts (ADR-CS-002). The engine
exists for the boundaries where structure can't reach:
- ingested legacy/third-party documents (evidence, not generated);
- issued snapshots vs later fact corrections (legitimate divergence —
  surfaced as "издаденият акт се разминава с текущите данни" info findings,
  resolvable by supersede or waive);
- semantic coherence (scope text vs table contents) where only rules/AI-
  suggestions can look.

Design consequence: consistency effort concentrates on **ingestion and
issuance boundaries**, not on generated drafts — those are consistent by
construction.

## 4. Reporting surfaces

- Per-project **findings board**: filter by severity/status/rule kind; each
  finding shows both sides with provenance links (page images later phases).
- **Pre-issuance checklist**: gate view per document ("за обр. 15 липсват:
  протокол 72ч Ел; отворен blocker: несъответствие на идентификатор").
- **Project health chip**: open blockers/warnings count on dashboards.
- All texts message-keyed, Bulgarian catalog (ADR-015).
