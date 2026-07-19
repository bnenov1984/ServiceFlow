# CS-21 — Provenance and Confidence

Status: Draft · Date: 18.07.2026 · The audit brief's core demand: every value
answers "source document, source page, confidence, extraction method, user
corrections, history."

## 1. Provenance record (attached to fact versions, and to legally
interesting entity attributes via the same mechanism — [10 §3](10_DATA_MODEL.md))

```
{ source_document_id, page, region (bbox/section, nullable),
  method: manual | native_text | table_parse | ocr | ai_text | ai_vision
          | computed | composed,
  confidence: numeric 0..1 (1.0 for manual/computed),
  proposal_id (when born from extraction),
  model_id + prompt_rev (when AI-born, via the batch) }
```

A fact may hold **multiple evidences** (permit number seen in РС itself, in
обр. 2, in the passport) — corroboration is first-class: agreeing evidences
strengthen, disagreeing ones surface conflicts ([16 §5](16_DOCUMENT_EXTRACTION_PIPELINE.md)).

## 2. Method semantics

- `manual` — human typed it; provenance may still cite the paper source
  ("from РС original") as a free reference.
- `native_text` / `table_parse` — deterministic extractors; confidence 1.0
  mechanically but still human-confirmed before fact-hood.
- `ocr` / `ai_*` — carry model confidence; **confidence never gates
  automation** (no auto-accept — [20 §7](20_AI_STRATEGY.md)); it orders review
  queues and colors the review UI.
- `computed` — formula key + inputs recorded ([18 §2](18_QUANTITY_CALCULATION_ENGINE.md)).
- `composed` — assembled from other facts (inventories, narratives); records
  the composer key + input fact versions.

## 3. History & corrections

Fact versions are append-only: every change = new version {author, reason,
timestamp} with its own provenance. The characteristic flows:

- extraction → accepted (v1, ai_text 0.87) → engineer corrects a digit
  (v2, manual, reason "OCR misread 6/8, checked original") — both retained;
- correction of a fact already frozen in an issued snapshot does **not**
  rewrite the snapshot; it raises the divergence info-finding
  ([19 §3](19_VALIDATION_AND_CONSISTENCY.md)) offering supersede/waive.

## 4. Confidence bands (UI language)

| Band | Range | Presentation |
|---|---|---|
| confirmed | human-resolved | plain (the only band generation ever sees) |
| high | ≥0.9 proposal | green in review queue |
| medium | 0.6–0.9 | yellow, review-prioritized |
| low | <0.6 | red, review-first, prefer re-scan/manual |

Bands are review-workflow furniture only — no semantic authority.

## 5. Why this design is load-bearing (not compliance theater)

- ДНСК scrutiny / disputes: the firm can show, years later and offline (the
  export includes provenance), why every number on a signed act was what it
  was.
- Model governance: per-type accuracy measurement needs method+model+outcome
  on every value ([20 §5](20_AI_STRATEGY.md)).
- Trust calibration inside the firm: engineers see instantly whether a value
  is someone's confirmed entry or a fresh OCR guess — the difference between
  a knowledge base and a data swamp.
