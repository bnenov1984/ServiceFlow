# CS-13 — Rules Engine

Status: Draft · Date: 18.07.2026 · Consumes the KB and dossier; produces
Findings. Validation layering: [19_VALIDATION_AND_CONSISTENCY.md](19_VALIDATION_AND_CONSISTENCY.md).

## 1. Design stance

Declarative **rule instances over a closed set of coded rule kinds**. Each
kind (required, format, cross-doc equality, chronology, tolerance,
completeness) is implemented once in typed, tested Python; concrete rules are
*data* — parameters + subscribed fact paths + severity + message key —
stored in `cs_rules` and versioned per rule set. No user-defined expression
language, no eval: new *kinds* are code PRs; new *rules* of existing kinds
are data. This keeps the engine auditable (a rule's meaning is testable code)
while keeping regulatory churn out of code (pragmatism directive; mirrors
ADR-CS-007's registry-as-data stance).

## 2. Rule kinds (v1 catalog)

| Kind | Parameters | Example (from real sample defects) |
|---|---|---|
| `required` | path, doc types, when (category/part) | обр. 14 must bind проектант-конструктор |
| `format` | path, pattern/type, normalizer | dates parse & are plausible (catches "20.04.12.2021"); ЕИК checksum; cadastral id shape |
| `cross_doc_equal` | path, scope (all docs of project) | cadastral identifier identical across passport §header, §1.4, and every act (catches the double-ПИ defect) |
| `cross_ref_match` | path A vs entity B | act's "образец N" label matches its document type (catches обр.7-header-обр.12-body) |
| `chronology` | ordering constraints between doc dates / fact dates | обр. 8 date ≥ pour date + curing days; обр. 14 ≥ max(structural acts); no act dated inside a suspension (обр.10→11) window; table dates within protocol period (catches 2020-in-2021) |
| `credential_validity` | participation role, credential kind | ДНСК удостоверение valid at act date |
| `quantity_tolerance` | metric, tolerance %, sources to compare | изпълнено vs проектно; act-declared vs computed ([18](18_QUANTITY_CALCULATION_ENGINE.md)) |
| `completeness` | required doc-type set per gate/category | Act 15 inventory covers every issued document; ПБ становище present before Act 15 |
| `uniqueness` | path scope | one active обр. 2 protocol; no duplicate issued numbers |

## 3. Evaluation model

- **Incremental**: rules subscribe to fact paths / doc events
  (`subscribed_paths`); a `FactConfirmed` or `DocumentIssued` event
  re-evaluates only affected rules (index rule→paths). In-process job via
  Core bus (ADR-011) + job pattern (ADR-006).
- **Full sweep**: nightly / on-demand per project, idempotent, reconciles
  drift (belt for the incremental suspenders).
- **Deterministic**: same KB state ⇒ same findings set. Findings are upserted
  by natural key (rule key + subjects) so re-evaluation never duplicates.
- **Explainable**: every finding carries subjects (both sides of a conflict:
  fact ids, doc ids, pages via provenance) and a bg message key + params
  (ADR-015 — the engine returns keys, the UI renders Bulgarian).

## 4. Severity & gates

- `blocker` — generation/issuance gates refuse (e.g. missing required
  signatory for обр. 14).
- `warning` — visible, waivable with reason (real projects have documented
  deviations — "частични недостатъци" is literally a field in обр. 14).
- `info` — advisory (e.g. изпълнено ≠ проектно but within tolerance).

Waivers: per finding, actor + reason, audited, survive re-evaluation (same
natural key), auto-reopen if the underlying values change afterwards.

## 5. AI's place (bounded)

AI may *suggest* candidate inconsistencies (e.g. semantic mismatch between
scope text and table contents) — these enter as `info`-severity findings of
kind `ai_suggested`, clearly labeled, never gating anything, and feed the
rule backlog when they prove precise (ADR-CS-003 discipline applied to rules).

## 6. Testing obligation

Every rule kind ships with fixture tests built from the sample defects
([02 §7](02_DOMAIN_KNOWLEDGE_BIBLE.md)): the identifier-drift passport, the
mislabeled обр. 7, the 2020/2021 protocol are committed (anonymized) as
regression fixtures — the engine must flag all three forever
([30 AC-4](30_ACCEPTANCE_CRITERIA.md)).
