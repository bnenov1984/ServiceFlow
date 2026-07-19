# Schemas

**Status: DRAFT — design artifacts, not yet consumed by any code.** These
JSON Schemas make the documentation's data contracts concrete and will become
the validation sources for manifests, extraction outputs, and the fact
taxonomy when implementation starts (Phase A/B). Draft 2020-12 dialect.

| Dir | Contents | Consumed by (future) |
|---|---|---|
| `project/` | project + participant shapes, fact taxonomy envelope | API layer, KB validation ([10_DATA_MODEL](../docs/10_DATA_MODEL.md)) |
| `documents/` | document-type registry entry shape | registry seed validation (ADR-CS-007) |
| `templates/` | template manifest schema | template upload/activation ([12_TEMPLATE_ENGINE](../docs/12_TEMPLATE_ENGINE.md)) |
| `workflows/` | document state machine + gate definition shape | registry/workflow validation ([14_WORKFLOW_ENGINE](../docs/14_WORKFLOW_ENGINE.md)) |
| `extraction/` | extraction result/proposal envelope per document type | AI/parser output validation — the quarantine's type gate (ADR-CS-003) |

Versioning: schemas carry `$id` with a version segment; breaking changes bump
the segment and require a migration note. CI (future) validates seed data and
committed manifests against these.
