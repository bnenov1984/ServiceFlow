# CS-29 — Risks and Open Questions

Status: Living document · Date: 18.07.2026

## 1. Open questions (decision needed, owner: PO unless noted)

| # | Question | Context | Default until decided |
|---|---|---|---|
| Q1 | **Normative verification**: current consolidated texts of Наредба №3/№5 — exact required signatories per form, current обр. 17 meaning, curing/decofring rules, amendment history | [02 §8](02_DOMAIN_KNOWLEDGE_BIBLE.md); asserted partly from practice samples | registry-as-data absorbs corrections; verify before declaring any template authoritative |
| Q2 | **Sample drawings**: none in the current corpus | [17](17_DRAWING_ANALYSIS_PIPELINE.md) is designed blind | phases C/D stay design-only until real drawing sets (with schedules) are provided |
| Q3 | Repository location mismatch: task named `C:\Projects\BusinessOS`; the actual Business OS repo is the ServiceFlow repo where this package now lives | ADR-CS-001 §Context | current location stands; a future repo move/rename is mechanical |
| Q4 | How far may tenant template overrides deviate from the normative layout? | [12 §5](12_TEMPLATE_ENGINE.md) | layout-only overrides; manifest hard rules immutable |
| Q5 | Legal analysis: GDPR erasure vs dossier integrity; КЕП e-signature validity for acts | [22 §5](22_AUDIT_AND_VERSIONING.md), [04 §3](04_STAKEHOLDERS_AND_ROLES.md) | anonymize-where-permitted; no e-signature claims in MVP |
| Q6 | Per-part permissions granularity | [04 §2](04_STAKEHOLDERS_AND_ROLES.md) | coarse roles + audit; revisit on pilot evidence |
| Q7 | Municipal/ДНСК digital submission channels | [01 §2](01_SCOPE_AND_GUARDRAILS.md) | out of scope; watch for stable APIs |
| Q8 | Client demand for local/on-prem AI (no external calls) | [20 §6](20_AI_STRATEGY.md) | not planned; opt-out = no AI features |
| Q9 | Fact path store: ltree vs text+check; taxonomy versioning mechanics | [10 §8](10_DATA_MODEL.md) | decide in first KB migration PR |
| Q10 | Numbering sequences ownership (with BOS-05 §1 / Етап 4) | [24 §4](24_INTEGRATION_WITH_BUSINESS_OS.md) | module-local, coordinated decision later |

## 2. Risks

| Risk | Likelihood/Impact | Mitigation |
|---|---|---|
| **Solo-dev focus split** with ServiceFlow (BOS-08 Phase 5 names this the big one) | H/H | business decision, not architecture; CS phases sized small; ServiceFlow plan keeps priority; Phase A has standalone value |
| Template fidelity distrust ("the act doesn't look exactly like ours") | M/H | start *from the firm's own files*; golden visual diffs; tenant layout overrides |
| Extraction quality below usefulness on scans | M/M | value front-loaded in non-OCR phases; deterministic-first; metrics before promises |
| Regulatory amendment mid-build | M/M | registry-as-data + versioned templates/rules with effective dates (ADR-CS-007) |
| KB taxonomy churn breaking bindings/rules | M/H | taxonomy versioned with migration notes; bindings validated in CI against taxonomy; golden generations catch breakage |
| Scope gravity toward "construction ERP" | M/H | CS-01 out-of-scope table is a review artifact; evidence rule |
| AI cost surprises | L/M | background-only, caching, per-tenant caps, model tiering ([20 §4](20_AI_STRATEGY.md)) |
| Over-generalization pressure ("make the template engine a platform now") | M/M | ADR-CS-006 + BOS Phase 6 discipline: two implementations before extraction |
| Legal exposure from a wrong generated value | L/H | provenance + human confirmation + validation gates + the firm signs on paper; positioning: preparation tool, authorship stays human |

## 3. Standing review triggers

Re-open this document when: pilot starts; each phase exit; any Наредба
amendment lands; BOS Phase 3 executes; a second CS-adjacent module idea
appears (extraction watchlist activates).
