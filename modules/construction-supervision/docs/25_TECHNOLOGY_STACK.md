# CS-25 — Technology Stack

Status: Draft · Date: 18.07.2026 · Rule: reuse the Business OS stack unless a
module need demands otherwise; every addition justified against the
pragmatism directive.

## 1. Inherited (no new decisions)

| Layer | Choice | Source |
|---|---|---|
| Backend | Python 3.12+/FastAPI/SQLAlchemy/Alembic, uv | ADR-003, repo standard |
| DB | PostgreSQL, RLS-first, JSONB where typed at edges | ADR-016, docs/08 |
| Frontend | React + TypeScript + Vite, feature folders, bg catalog | ADR-004, docs/15 |
| Jobs | DB-backed in-process jobs | ADR-006 |
| Files | Core storage port (fs/S3 per deployment) | ADR-007 |
| Events | in-process bus | ADR-011 |
| Testing | pytest + vitest + import-linter + architecture tests | docs/12, BOS Phases 1–2 |

## 2. Module additions (each with the reason and the rejected alternative)

| Need | Choice | Why / rejected |
|---|---|---|
| DOCX generation | **python-docx + docxtpl-style substitution behind our own renderer interface** | mature, pure-Python; logic stays in our manifest layer, the lib only substitutes ([12 §4](12_TEMPLATE_ENGINE.md)). Rejected: HTML→DOCX (layout loss), COM automation (Windows server dependency), Jinja-in-docx as *authoring* model (ADR-CS-004) |
| DOCX→PDF preview | LibreOffice headless (jobized) | boring, standard; PDF is convenience only ([15 §5](15_DOCUMENT_GENERATION_PIPELINE.md)) |
| PDF parsing (born-digital) | PyMuPDF + pdfplumber | text+geometry, table heuristics; both battle-tested |
| DOCX parsing | python-docx (reading) | already proven on the real samples during this discovery |
| OCR (phase C) | Tesseract (bul) baseline; model-vision escalation for degraded pages | local-first cost control; escalation is quarantined AI ([20 §3](20_AI_STRATEGY.md)). Rejected as default: cloud-OCR-everything (cost, privacy) |
| AI | Anthropic API (claude-haiku-4-5 / claude-sonnet-5 / claude-fable-5 tiers), structured outputs, prompts versioned in-repo | [20](20_AI_STRATEGY.md) |
| Table extraction from drawings (C/D) | pdfplumber/camelot-class first; vision on cropped regions as fallback | [17](17_DRAWING_ANALYSIS_PIPELINE.md) |
| JSON Schema validation | jsonschema/Pydantic v2 | manifests, extraction outputs, taxonomy ([schemas/](../schemas/README.md)) |
| Image preprocessing (C) | Pillow + OpenCV (deskew/binarize) | standard OCR hygiene |

## 3. Explicitly not added

- No new datastore (no Mongo/vector DB/Redis requirement in MVP scope).
- No message broker; no separate worker fleet until job evidence (Core ask
  path — [24 §4](24_INTEGRATION_WITH_BUSINESS_OS.md)).
- No workflow engine product ([14 §5](14_WORKFLOW_ENGINE.md)).
- No microservices (ADR-BOS-001 reaffirmed).
- No client-side document rendering stack.

## 4. Dependency governance

All new Python deps enter through the module's own extras group in the shared
backend project, pinned via uv; each carries a one-line justification in the
PR. Parsing libs touching untrusted uploads run in jobs with resource limits
([23 §5](23_SECURITY_AND_PERMISSIONS.md)).
