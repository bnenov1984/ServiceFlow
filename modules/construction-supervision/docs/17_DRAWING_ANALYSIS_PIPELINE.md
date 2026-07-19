# CS-17 — Drawing Analysis Pipeline

Status: Draft · Date: 18.07.2026 · Phase C/D capability — designed now so the
data model doesn't paint us into a corner, built only against real drawing
sets ([29 Q2](29_RISKS_AND_OPEN_QUESTIONS.md): sample drawings needed).

## 1. Scope honesty (assumption challenged per the brief)

"Read construction drawings" ranges from trivial to research-grade. Ranked by
value ÷ feasibility:

| Target | Feasibility | Value | Phase |
|---|---|---|---|
| **Title blocks** (антетки: project, part, sheet, scale, revision, designer) | High — fixed zones, vector text | drawing registry autofill, cross-doc consistency inputs | C |
| **Schedule tables** (спецификации: armature schedules, элемент lists, кофражни таблици) | High for vector PDFs — table extraction | the quantity goldmine: rebar by class/diameter, element dimensions | C |
| **Dimension/annotation harvest** (levels, sections, axes) | Medium | element geometry hints, level list | D |
| **Full plan geometry understanding** (element recognition from linework) | Low/research | replaces manual element entry | not planned; revisit on evidence |

Structural *schedules* carry most quantity data in Bulgarian practice —
the pipeline's center of gravity is table extraction, not computer vision on
linework.

## 2. Pipeline

```
1 REGISTER   drawing → SourceDocument(kind=drawing) + Drawing/Sheet rows
2 TRIAGE     vector PDF vs raster scan (per page)
3 TITLE      title-block extraction: zone heuristics per firm convention
             (configurable zones), vector text first, OCR fallback;
             → proposals (drawing metadata)
4 TABLES     schedule detection & extraction:
             vector: ruled-table geometry (pdfplumber/camelot-class)
             raster: OCR + table structure model (phase D)
             → typed rows against schedule schemas (rebar schedule,
               element schedule) → proposals for StructuralElements /
               quantity claims
5 AI ASSIST  where deterministic table parse fails: vision model reads the
             cropped table region only (not the whole sheet), output
             schema-constrained, page/bbox anchors — same quarantine as 16 §3
6 REVIEW     same proposal review UI; elements/quantities land in
             Drawings & Quantities context, provenance → sheet/region
```

## 3. Revisions

Drawings arrive in revisions (преработки, екзекутиви). A new revision of a
sheet supersedes its predecessor's extracted claims: affected proposals/
elements flagged for re-review, quantity comparisons re-run — a drawing
revision is a first-class event, not a file swap.

## 4. What the module trusts

Extracted drawing data is *evidence*, never authority: elements sourced from
schedules keep `source=schedule` + provenance; a conflicting manual
measurement or act-declared quantity produces a finding for a human. The
KB remains the single truth; drawings are its best witnesses.
