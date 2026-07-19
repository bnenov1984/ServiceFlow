# ADR-CS-004 — Word templates are presentation-only; logic lives in manifests

Status: Proposed (PO review) · Date: 18.07.2026

## Context

The firm's institutional knowledge is embodied in Word files (the samples).
Word is the right authoring medium for legal layout — and a terrible medium
for logic: invisible in diffs, unreviewable, fragile across saves (run
fragmentation), and editable by anyone with the file.

## Decision

1. A template is a versioned **pair**: visual `.docx` + machine-readable
   **manifest** (JSON, schema-validated). All bindings, requiredness,
   conditions, loops, calculations, and composition logic live in the
   manifest ([12](../12_TEMPLATE_ENGINE.md)).
2. Placeholders in the .docx are **names and block ids only** — no
   expressions, no conditions-in-Word. A layout editor can restyle and
   reposition; only a reviewed manifest change can alter behavior.
3. Calculations and composers are referenced **by key** into code registries
   (typed, tested) — no eval of data-supplied expressions, ever
   (also a security decision, [23 §5](../23_SECURITY_AND_PERMISSIONS.md)).
4. The pair versions atomically with effective dates; issued documents pin
   their template version forever.

## Consequences

- Two audiences, cleanly split: PO/engineers own layout in Word; developers
  own manifests in code review.
- Requires a placeholder-hygiene check (unbound placeholder / unused binding
  = template validation error) — cheap, and it catches the template drift
  class before production.
- Slightly more ceremony than Jinja-in-docx; accepted — the ceremony *is*
  the review boundary.

## Rejected

- Jinja2-in-docx as authoring model (logic drifts into Word).
- Layout-in-code (HTML→DOCX) — loses the exact trusted legal layouts.
- Storing manifests inside the .docx (custom XML parts) — hides the logic
  from diffs again; keep them side-by-side artifacts.
