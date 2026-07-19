# CS-07 — Domain Model

Status: Draft · Date: 18.07.2026 · DDD-style conceptual model; persistence in
[10_DATA_MODEL.md](10_DATA_MODEL.md); context boundaries in
[08_BOUNDED_CONTEXTS.md](08_BOUNDED_CONTEXTS.md).

## 1. Aggregate map (overview)

```
ConstructionProject (root of the vertical)
 ├── Permit (1..n incl. amendments)
 ├── CadastralIdentifier (1..n, typed)
 ├── Participation (n)  ──references──▶  Party (firm-level library)
 ├── ProjectPhaseState (derived)
 └── Timeline (append-only)

KnowledgeBase (per project)
 └── Fact (n)  ── FactVersion history, Provenance ──▶ SourceDocument/page

SourceDocument (per project)      DocumentType (registry, firm/global)
 └── SourcePage (n)                ├── TemplateVersion (visual + manifest)
                                   ├── RuleSet
ExtractionBatch                    └── WorkflowDefinition
 └── ExtractionProposal (n)
                                  GeneratedDocument (per project, per type)
Drawing / DrawingSheet             └── GeneratedDocumentVersion
 └── StructuralElement (n)              └── DataSnapshot (frozen facts)
      └── QuantityLine (computed)
                                  Finding (per project, from rules)
```

## 2. ConstructionProject

The aggregate root. Identity, category (with legal basis чл. 137), status
**derived** from issued documents (never a free-standing editable field —
prevents the classic "status says живо, documents say приет" drift).

Invariants:
- exactly one active permit chain; amendments ordered;
- cadastral identifiers typed (land plot / building / facility) and unique
  per kind+value within the project — the sample's double-identifier defect
  becomes structurally impossible to *store* silently (it can still be
  *reported* about source documents).

## 3. Fact — the atom of the knowledge base

A Fact is a typed, addressable value: `(project, path, value, unit?, status)`
where `path` is a stable dotted address from the module's fact taxonomy
(e.g. `permit.number`, `identification.cadastral.building`,
`participants.builder.eik`). Facts carry:

- **type discipline**: date, quantity(+unit), identifier, enum, text, ref;
- **status**: `proposed` (from extraction, not authoritative) → `confirmed`
  (human) — only confirmed facts feed generation;
- **provenance** (1..n evidences): source doc/page/region, method, confidence;
- **version history**: every change is a new FactVersion with author+reason.

Design choice — *taxonomy-typed KB, not EAV free-for-all*: the fact path
vocabulary is a versioned schema owned by the module
([schemas/project/](../schemas/README.md)), so rules and bindings address
facts reliably. Well-known high-traffic entities (Permit, Participation,
StructuralElement) are **first-class entities**, not facts; the Fact store
covers the long tail (passport characteristics, narrative inputs). The full
split is defined in [10_DATA_MODEL.md §3](10_DATA_MODEL.md). This is the
module's answer to "no EAV platform" (BOS-00 §6) — typed entities where the
shape is known, one disciplined fact store where it is regulatorily long-tailed.

## 4. Party and Participation

- **Party** (firm library): person or company with typed credentials
  (Удостоверение ДНСК, КИИП/КАБ, diploma, ЦПРС, ЕИК) each with validity
  window. Reused across projects.
- **Participation** (project-scoped): Party in a role, optionally per part
  (проектант част СК), time-bounded, with appointing evidence (договор,
  заповед №). The builder-change sample: two builder Participations, disjoint
  periods, обр. 10/11 documents as boundary evidence.
- **At issuance, participant attributes are snapshotted** into the document
  version (a signed act shows the удостоверение number as it read that day —
  later corrections to the library must not rewrite history). Rule: live data
  in Party/Participation; frozen copies only inside DataSnapshot (consistent
  with ADR-CS-002's "no duplicated *live* state").

## 5. DocumentType (registry as data — ADR-CS-007)

`document_type` = { internal id (`act_12`, `act_14`, `act_15`,
`technical_passport`, `test_protocol_72h`, …), normative citation, practice
aliases ("акт 17"), category applicability, required participant roles,
template versions, rule set, workflow definition, dossier ordering hints }.
Adding обр. 6 is data + a template pair — no code.

Act 14 is **not** a variant of act 12/15: own type, template, rules
(structure-part participants; requires the structural chain), workflow gate
(unlocks довършителни работи), and output. Same независимост for every form
(ADR-CS-005).

## 6. GeneratedDocument

Per project+type instances (обр. 12 recurs dozens of times — instances carry
sequence numbers and subject, e.g. "обр. 12 — армировка основи"). Versioned:
draft versions regenerate freely; **issuance** freezes a DataSnapshot (all
facts + participant attributes used, template version, rendered file hash).
Superseding an issued document is a formal act (new version + reason),
mirroring the immutability discipline of ServiceFlow invoices (BR-2).

## 7. SourceDocument and extraction objects

SourceDocument: imported file, classified against DocumentType (or
`external` kinds: permit, certificate, drawing, contract). A combined file
(актове-къща) is one SourceDocument split into many logical **SourceSections**
each mapped to its own act instance — the file's packaging never leaks into
the domain (ADR-CS-005).

ExtractionBatch → ExtractionProposals: candidate `(path, value, anchor,
confidence, method)` tuples. Proposals are a separate aggregate; accepting
one creates/updates a Fact with provenance pointing back. Rejection retains
the proposal for audit and model evaluation ([20 §5](20_AI_STRATEGY.md)).

## 8. Drawing, StructuralElement, QuantityLine

Drawing (per part, revision-aware) → sheets. StructuralElement: typed
(foundation, column, wall/шайба, beam, slab, roof member) with geometry
attributes and level; sourced from schedules (extraction) or manual entry.
QuantityLine: computed quantity (concrete m³, formwork m², rebar kg by class
and diameter) with the formula inputs recorded — reproducible, explainable
([18](18_QUANTITY_CALCULATION_ENGINE.md)). Comparisons against act-declared
quantities produce Findings, never silent adjustments.

## 9. Finding

`(rule id, severity, subjects[], message key + params, status)` — subjects
reference facts/documents/participations on both sides of a conflict.
Lifecycle: open → acknowledged → resolved | waived(reason, actor). Waivers
are legitimate (real projects have documented deviations) but auditable.

## 10. Domain events (in-process, Core bus — ADR-011)

`FactConfirmed`, `FactCorrected`, `SourceRegistered`, `ProposalAccepted/
Rejected`, `DocumentGenerated`, `DocumentIssued`, `FindingRaised/Resolved`,
`PhaseGatePassed`. Consumers: timeline projection, findings recompute,
dossier index. Events never cross module boundaries except via declared
contracts ([24 §3](24_INTEGRATION_WITH_BUSINESS_OS.md)).
