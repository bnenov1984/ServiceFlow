# CS-10 — Data Model

Status: Draft · Date: 18.07.2026 · Conventions: every table has UUIDv7 `id`
(`shared_kernel.ids.new_id`) + `company_id` FK + RLS FORCE policy (ADR-013/016);
`created_at/updated_at` timestamptz; money/quantities `numeric`; soft delete
only where legally required (sources). Table prefix `cs_` prevents collision
with ServiceFlow/Core tables in the shared schema. No migrations exist yet —
this is the blueprint the first Alembic revision will implement.

## 1. Project Registry

```
cs_projects            name, category (enum I..VI), category_legal_basis,
                       status_cached (derived, trigger-refreshed), notes
cs_cadastral_ids       project_id, kind (land_plot|building|facility|planning),
                       value, is_current    UNIQUE(project_id, kind, value)
cs_permits             project_id, number, issued_on, issuer, kind
                       (original|amendment), parent_permit_id, approved_parts jsonb
cs_parties             kind (person|company), names, eik, address,
                       details jsonb (typed by kind)
cs_party_credentials   party_id, kind (dnsk_cert|kiip|kab|diploma|cprs|mrrb_list),
                       number, issuer, issued_on, valid_until, details jsonb
cs_participations      project_id, party_id, role (enum: client|builder|
                       tech_manager|designer|supervisor_specialist|consultant|
                       authors_supervision), part (nullable enum: arch|struct|
                       el|vik|geo|ee|fire|hvac), valid_from, valid_to,
                       appointed_by_doc_id (nullable → cs_source_documents)
```

## 2. Sources & Extraction

```
cs_source_documents    project_id, kind (act|permit|certificate|drawing|
                       contract|other), doc_type_id (nullable), title,
                       file_sha256, storage_key, page_count, status
                       (uploaded|classified|parsed|reviewed|archived)
cs_source_sections     source_document_id, page_from, page_to, label,
                       doc_type_id  -- split of combined files (ADR-CS-005)
cs_extraction_batches  source_document_id, method (native_text|table_parse|
                       ocr|ai_vision|ai_text), model_id, prompt_rev, status,
                       cost_meta jsonb
cs_extraction_proposals batch_id, fact_path, proposed_value jsonb,
                       unit, anchor jsonb (page, bbox/section), confidence
                       numeric, status (proposed|accepted|corrected|rejected),
                       resolved_by_user_id, resolved_at, resulting_fact_id
```

## 3. Knowledge Base

First-class entities above (permits, participations…) hold the *shaped* data.
`cs_facts` holds the long tail (passport characteristics, narrative inputs,
per-document free fields), addressed by taxonomy path:

```
cs_facts               project_id, path (ltree/text, taxonomy-validated),
                       value jsonb (typed envelope: {t:"date"|"qty"|"text"|
                       "ident"|"enum"|"ref", v:..., unit?}),
                       status (confirmed), current_version_id
                       UNIQUE(project_id, path[, discriminator])
cs_fact_versions       fact_id, value jsonb, author_user_id, reason,
                       created_at  -- append-only
cs_fact_provenance     fact_version_id, source_document_id, page, region jsonb,
                       method, confidence, proposal_id (nullable)
```

Entity rows get provenance/versioning too where legally interesting, via the
same `cs_fact_provenance` pattern pointed at entity+column (subject_type,
subject_id, attribute) — one provenance mechanism, two kinds of subjects
([21](21_PROVENANCE_AND_CONFIDENCE.md)).

## 4. Document Production

```
cs_document_types      internal_key (act_12|act_14|act_15|technical_passport|...),
                       title_bg, normative_citation, practice_aliases text[],
                       applicable_categories int[], required_roles jsonb,
                       dossier_order, active
cs_templates           doc_type_id, name
cs_template_versions   template_id, version, docx_storage_key, manifest jsonb
                       (validated against schemas/templates/*.json),
                       effective_from, status (draft|active|retired)
cs_generated_documents project_id, doc_type_id, instance_label
                       (e.g. "армировка основи"), sequence_no, current_state
cs_generated_versions  generated_document_id, version, template_version_id,
                       state (draft|prepared|issued|superseded),
                       data_snapshot jsonb (facts+participants as rendered),
                       rendered_sha256, storage_key, issued_number, issued_on,
                       issued_by_user_id, supersede_reason
```

Issued versions are immutable: UPDATE forbidden by trigger except state →
superseded (with reason); snapshots never rewritten (BR-2-style discipline).

## 5. Drawings & Quantities (phase C/D tables, designed now, created then)

```
cs_drawings            project_id, part, title, revision, source_document_id
cs_drawing_sheets      drawing_id, sheet_no, scale, title_block jsonb
cs_structural_elements project_id, kind (foundation|column|wall|beam|slab|roof),
                       label (K1, Ш2…), level, geometry jsonb (typed per kind),
                       concrete_class, source (schedule|manual|ai), 
                       drawing_sheet_id (nullable)
cs_quantity_lines      project_id, subject (element|level|project), subject_id,
                       metric (concrete_m3|formwork_m2|rebar_kg),
                       breakdown jsonb (per steel class/diameter),
                       value numeric, formula_key, inputs jsonb, computed_at
```

## 6. Compliance & Dossier

```
cs_rule_sets           doc_type_id (nullable = project-wide), version, active
cs_rules               rule_set_id, key, kind (required|format|cross_doc|
                       chronology|quantity_tolerance|completeness),
                       severity (blocker|warning|info), params jsonb,
                       message_key, subscribed_paths text[]
cs_findings            project_id, rule_key, severity, status (open|ack|
                       resolved|waived), subjects jsonb, message_key,
                       message_params jsonb, waive_reason, waived_by, timestamps
cs_workflow_states     generated_document_id … (or folded into
                       cs_generated_documents.current_state + transitions log)
cs_transitions         subject_type, subject_id, from_state, to_state,
                       actor_user_id, at, note  -- append-only
cs_timeline_events     project_id, kind, subject refs, payload jsonb, at
                       -- append-only projection (ADR-011 pattern)
```

## 7. Integrity rules worth stating

- FK graph is tenant-consistent: composite FKs or triggers ensure children's
  `company_id` equals parent's (same pattern as ServiceFlow tables).
- `cs_extraction_proposals.status='accepted'` requires `resulting_fact_id` —
  the AI quarantine is a DB constraint, not app courtesy (ADR-CS-003).
- A `cs_generated_versions.state='issued'` row requires `issued_on`,
  `issued_number`, `data_snapshot`, `rendered_sha256` NOT NULL.
- `cs_facts` deletion forbidden while any snapshot references its path for
  the project (soft-retire instead) — history must stay explainable.

## 8. Open data questions

→ consolidated in [29_RISKS_AND_OPEN_QUESTIONS.md](29_RISKS_AND_OPEN_QUESTIONS.md):
document numbering sequences ownership (BOS-05 §1 parallel), ltree vs text
for paths, whether participants deserve global (cross-tenant) master data
(no — privacy; per-tenant only, revisit never without a lawyer).
