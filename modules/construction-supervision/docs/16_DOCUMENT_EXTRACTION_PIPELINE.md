# CS-16 — Document Extraction Pipeline

Status: Draft · Date: 18.07.2026 · The inbound half
([09 §3.1](09_SYSTEM_ARCHITECTURE.md)); AI boundaries in
[20_AI_STRATEGY.md](20_AI_STRATEGY.md); drawings split out into
[17_DRAWING_ANALYSIS_PIPELINE.md](17_DRAWING_ANALYSIS_PIPELINE.md).

## 1. When extraction earns its keep

Primary value cases (CS-01 §5 challenge, restated):
1. **Legacy/mid-stream projects** — a firm adopting the system with 15 live
   projects imports existing acts instead of re-typing them.
2. **Third-party inputs** — permits, скици, material declarations, control
   protocols arrive as PDFs the firm didn't author.
3. **The combined-file reality** — актове-къща.docx-style bundles must be
   split and mined.
New projects born in the system need almost none of this — structured entry
is faster. The pipeline is therefore phase B, not MVP core.

## 2. Stages

```
1 REGISTER   upload → storage port, sha256, SourceDocument row
2 TRIAGE     format sniff: born-digital PDF / DOCX / scan (image or
             image-only PDF)
3 CLASSIFY   document type + section splitting for bundles
             MVP-B: manual pick + manual split points, model-assisted later;
             classification confidence recorded either way
4 PARSE      deterministic first (ADR-CS-003 preference order):
             • DOCX: python-docx tree → paragraphs/tables (the sample
               extractor already proves this works on the real files)
             • PDF born-digital: text + table geometry (pdfplumber/PyMuPDF)
             • templates-known forms: positional/regex extractors per
               document type (header block, works tables, signature lists)
5 OCR        scans only (phase C): image preprocess → OCR (bg) → same
             downstream path; page images retained for anchors
6 AI-EXTRACT residual fields deterministic parsing missed, or low-structure
             prose (scope descriptions): schema-constrained model call per
             document type; outputs must validate against the type's
             extraction schema (schemas/extraction/) or are discarded
7 NORMALIZE  dates (bg formats, the "202г." typo class), units vocabulary,
             identifiers (cadastral shape, ЕИК checksum), names
             (transliteration variants) — deterministic normalizers, tested
8 PROPOSE    ExtractionProposals: (fact path, value, anchor page/region,
             method, confidence); duplicates vs existing facts detected and
             presented as confirm/conflict, not blind inserts
9 REVIEW     human accepts / corrects / rejects; acceptance ⇒ Fact +
             provenance; corrections feed the eval set (20 §5)
```

Stages 4–8 run as background jobs (Core ADR-006), idempotent per
(source, batch); re-running a batch supersedes its unresolved proposals.

## 3. The quarantine invariant (restated as pipeline law)

No stage may write to `cs_facts`. Only stage 9's human acceptance does,
through the KB service. Enforced by DB constraint (proposal→fact linkage) and
module layering — an AI adapter literally has no import path to the KB write
service ([26 §import rules](26_REPOSITORY_STRUCTURE.md)).

## 4. Per-type extractors (deterministic, the workhorses)

The known forms are *forms*: fixed header blocks, fixed clause skeletons,
one works table. A per-type extractor = anchor phrases + field zones +
table shape, versioned alongside the document type registry entry. The nine
обр. 12 instances in the combined sample are the calibration corpus: a
correct extractor must pull строеж/РС/participants/date/scope/works-rows
from all nine with zero AI calls. AI covers what remains (free prose,
degraded scans, unknown layouts).

## 5. Conflict handling

An extracted value that contradicts a confirmed fact (permit number differs
across two sources) never overwrites: it becomes a **conflict proposal**
surfaced with both provenances side by side; resolution is a human choice
that leaves both evidences recorded on the fact's history. This is how
identifier drift (sample defect №1) is *caught at ingestion* instead of
propagated.

## 6. Metrics (built in from the start)

Per batch: fields proposed / auto-parse share vs AI share / acceptance rate /
correction rate / time-to-review. These decide where deterministic extractors
replace AI (target: AI share falls per type over time) and feed
[20 §5 evaluation](20_AI_STRATEGY.md).
