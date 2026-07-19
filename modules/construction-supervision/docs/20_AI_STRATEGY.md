# CS-20 — AI Strategy

Status: Draft · Date: 18.07.2026 · Governing decision: ADR-CS-003
(deterministic core, AI as quarantined proposer).

## 1. Role charter

| AI may | AI may never |
|---|---|
| extract candidate facts from documents/scans (schema-constrained) | write to the knowledge base |
| read tables & title blocks where deterministic parsing fails | appear in the generation/render path |
| classify/split incoming documents (assist) | decide a gate or issue a document |
| draft predefined narrative paragraphs from structured inputs, for human approval | invent a value absent from sources |
| suggest inconsistencies (info-level, labeled) | raise blocker findings |
| summarize technical descriptions for review UIs | be a chat interface to project data (not in scope) |

## 2. Architectural containment (how "never" is enforced)

- AI clients live in the Ingestion adapters layer only; no import path to KB
  write services ([26](26_REPOSITORY_STRUCTURE.md) lint rule).
- Outputs must validate against per-type extraction schemas
  ([schemas/extraction/](../schemas/README.md)); invalid ⇒ discarded, logged.
- Every accepted value carries method+model+confidence provenance forever —
  "where did this number come from" always answerable ([21](21_PROVENANCE_AND_CONFIDENCE.md)).
- DB constraint: proposals only become facts through human resolution rows
  ([10 §7](10_DATA_MODEL.md)).

## 3. Model usage (per task, current Claude family)

| Task | Model class | Notes |
|---|---|---|
| Document classification/splitting | claude-haiku-4-5 | cheap, high-volume |
| Field extraction from known forms (text) | claude-sonnet-5 | structured outputs, per-type schemas |
| Vision: scans, table regions, title blocks | claude-sonnet-5 (vision) | cropped regions, not whole sheets, to control cost & focus |
| Narrative drafting (Act 15 part texts) from structured inputs | claude-sonnet-5 | temperature-low, template-guided, human approves |
| Hard/degraded documents, disagreement arbitration | claude-fable-5 | escalation tier only |

Principles: smallest sufficient model; deterministic extractors *replace* AI
per type as they mature (measured — [16 §6](16_DOCUMENT_EXTRACTION_PIPELINE.md));
prompts and few-shots versioned in-repo per document type; model id + prompt
revision recorded on every batch (`cs_extraction_batches`).

## 4. Cost & latency posture

Extraction is background work — batch, retry, no interactive SLA. Budget
guardrails per tenant (monthly cap, visible usage), caching by content hash
(same source page never re-extracted for the same prompt revision). Expected
steady-state: AI touches a minority of fields (forms are forms) — the
economics *improve* with adoption, unlike generate-with-AI architectures.

## 5. Evaluation loop

The review UI's accept/correct/reject stream is a labeled dataset by
construction. Per document type: precision/recall per field, correction
distance, reviewer time. Golden extraction sets from the samples (the nine
обр. 12 instances, the passport) run in CI against prompt/model changes —
a prompt bump that drops обр. 12 header recall fails the build. Rejected/
corrected proposals are retained (audit + future fine-tuning option).

## 6. Privacy & compliance

- Tenant-level opt-in for external model calls; processing documented
  (GDPR processor note); zero-retention API options preferred.
- Redaction pass for ЕГН patterns before any external call (defensive — acts
  normally carry names/credential numbers, not ЕГН; if present, masked).
- No cross-tenant mixing in prompts/few-shots; examples from the product's
  own anonymized corpus only.
- On-prem/local-model fallback is *not* planned (pragmatism; revisit only on
  a paying client's hard requirement — [29 Q8](29_RISKS_AND_OPEN_QUESTIONS.md)).

## 7. Rejected AI architectures (challenged per the brief)

- **RAG/chat over the dossier** — different product; the KB *is* the
  structured answer surface; retrieval-into-prose reintroduces invention risk.
- **"AI fills the Word template directly"** — unauditable, nondeterministic,
  violates SSOT; the whole design exists to prevent this.
- **Agentic auto-acceptance above a confidence bar** — tempting, rejected for
  legal documents; confidence gates *review priority order*, never skips
  review. Revisit per-field only with per-type precision evidence ≥ target
  over months, and even then opt-in per tenant.
