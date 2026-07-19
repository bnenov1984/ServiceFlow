# CS-12 — Template Engine

Status: Draft · Date: 18.07.2026 · Binding decision: ADR-CS-004 (Word is
presentation-only).

## 1. The two-artifact model

A template is a **pair**, versioned together as one TemplateVersion:

1. **Visual template** — a `.docx` authored in Word by a human who cares
   about how the act looks (the firm already has these — the sample templates
   are the starting material). It contains only *placeholders* and layout.
2. **Manifest** — machine-readable JSON (schema:
   [schemas/templates/template-manifest.schema.json](../schemas/README.md))
   declaring every placeholder's meaning: source binding, requiredness,
   formatting, conditions, loops, calculations. **All logic lives here.**

Rationale: Word files are diff-hostile, logic hidden in them is unreviewable
and unversionable; conversely, layout in code is unmaintainable by the PO.
The pair splits the concerns exactly along the people who maintain them.

## 2. Placeholder language (in .docx)

Deliberately minimal — placeholders are *names*, not expressions:

```
{{permit.number}}                     scalar field
{{#works_table}} … {{/works_table}}   repeatable region (table rows, lists)
{{?has_partial_defects}} … {{/?}}     conditional block (id, not expression!)
```

Conditions and loops are **referenced by id**; their logic (the actual
predicate, the row source, sort order) is defined in the manifest. A Word
author can move/restyle a block but cannot change *when* it appears — that is
a reviewed manifest change. This is the enforcement mechanism for ADR-CS-004,
not just a convention.

## 3. Manifest capabilities

| Capability | Manifest declaration |
|---|---|
| Static text | lives in the .docx, untouched |
| Dynamic field | `{ph, source: fact path / entity attr / context var, format (date bg, number, unit), required: hard\|soft, fallback: none}` — hard-required + missing ⇒ generation refuses (NFR-2) |
| Conditional block | `{block_id, predicate: declarative expr over paths (exists, eq, in, count>), else_block?}` |
| Loop table | `{block_id, row_source: query key (e.g. works_lines, dossier_inventory, participants[role=designer]), sort, row bindings, empty_behavior: omit\|placeholder_row}` |
| Calculated field | `{ph, calc_key}` — calc registered in code (typed, tested), never an eval'd expression in data ([18](18_QUANTITY_CALCULATION_ENGINE.md) supplies the heavy ones) |
| Composed summary | `{ph, composer_key}` — assembles prose from structured inputs (Act 15 part narratives); AI-drafted variants enter only as *reviewed fact text* upstream, the composer itself is deterministic |
| Common blocks | manifest `includes` — the shared header block defined once, included by every act manifest (§1.4 of [11](11_DOCUMENT_MODEL.md)) |

## 4. Rendering

Renderer: python-docx/docxtpl-class library ([25 §3](25_TECHNOLOGY_STACK.md))
operating on the visual template with a fully *resolved* context — binding
resolution, condition evaluation, and row expansion happen **before**
touching the .docx, in plain tested Python. The renderer only substitutes
and clones; it holds no logic. Output normalization (zip timestamps, rsid
stripping) makes renders byte-comparable (NFR-1).

## 5. Versioning & lifecycle

- TemplateVersion: `draft → active → retired`, with `effective_from`.
  Generation always records which version produced a document; issued
  snapshots pin it forever ([22](22_AUDIT_AND_VERSIONING.md)).
- A regulatory amendment = new version with new effective date; both live
  side by side; the registry picks by document date.
- Manifest changes are code-review-grade events (JSON diff in PR); .docx
  changes are verified by golden-file render tests against sample data
  ([30 AC-2](30_ACCEPTANCE_CRITERIA.md)).
- Template ownership: global built-ins (maintained with the product,
  normative forms) + tenant-level overrides (firm letterheads, practice
  variants). Tenant overrides may change *layout*, not manifests' hard
  requirements: override = new visual + inherited manifest, deviations
  flagged. (Open question on how far overrides may go: [29 Q4](29_RISKS_AND_OPEN_QUESTIONS.md).)

## 6. Authoring workflow (who does what)

1. Start from the firm's existing .docx (the samples).
2. Replace variable text with placeholders (assisted: a "templatize" tool
   diffs two filled instances of the same form and proposes placeholder
   sites — the combined file's 9 обр.12 instances are perfect input).
3. Write/generate manifest skeleton from placeholders; bind to taxonomy paths.
4. Golden-render against a sample project; visual diff vs. the original.
5. Activate with effective date.

## 7. Explicitly rejected

- Expression language inside Word (Jinja in docx): logic drifts into an
  unreviewable medium — violates ADR-CS-004.
- HTML→DOCX conversion: loses the firm's exact legal layout, the thing they
  trust most.
- "AI writes the whole document each time": violates ADR-CS-003 and the core
  SSOT premise; AI appears only upstream of facts, never in rendering.
