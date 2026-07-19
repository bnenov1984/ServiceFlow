# CS-23 — Security and Permissions

Status: Draft · Date: 18.07.2026 · Baseline: Business OS security model
(ServiceFlow docs/11, ADR-008, ADR-016) applies wholesale; this document
covers only module specifics.

## 1. Tenancy (inherited, restated as obligation)

- Every `cs_*` table: `company_id`, RLS `FORCE`, fail-closed GUC; queries via
  the scoped chokepoint; app role never superuser. Isolation tests for the
  module's tables join the P0 suite **from the first migration**.
- Files: storage keys namespaced per tenant; the storage port must not allow
  cross-tenant key access (existing Core guarantee — verified by module P0
  test with two tenants' files).

## 2. Authentication & sessions

Business OS identity as-is (session auth, PIN switching, CSRF, owner gate)
via `identity.deps` / `identity.contracts` only (BOS-16 boundary — the module
must not import identity internals; import-linter enforced).

## 3. Authorization matrix (MVP — deliberately coarse, [04 §2](04_STAKEHOLDERS_AND_ROLES.md))

| Capability | Owner/Manager | Engineer | Office |
|---|---|---|---|
| Manage users, roles, templates, rule activation | ✓ | — | — |
| Create/edit projects, permits, participants | ✓ | ✓ | ✓ |
| Upload sources, run extraction | ✓ | ✓ | ✓ |
| Accept/correct extraction proposals | ✓ | ✓ | — |
| Confirm/edit facts | ✓ | ✓ | drafts only |
| Generate drafts | ✓ | ✓ | ✓ |
| **Issue documents** (incl. supersede) | ✓ | — | — |
| Waive findings | ✓ | ✓ (warnings only) | — |
| Export dossier | ✓ | ✓ | — |

Issuance is the module's "owner gate" analogue — the manager signs, the
manager issues. Per-part granularity deliberately deferred (evidence rule).

## 4. Data protection specifics

- PII inventory: party names, addresses, diploma/register numbers, scans
  containing signatures. Never in logs (repo rule 7); excluded from
  telemetry; masked in error contexts.
- Signed-act scans are the most sensitive artifacts (handwritten signatures):
  stored via storage port, access logged, included in exports only with
  explicit selection.
- External AI calls: tenant opt-in + redaction ([20 §6](20_AI_STRATEGY.md)).
- Backups/restore drills cover DB + files as one consistent set (NFR §3).

## 5. Threat notes (module-specific)

- **Template injection**: manifests are data — renderer must treat bindings
  as values, never evaluate placeholder content; manifest schema validation
  on upload; only managers upload templates (and in MVP, only product-shipped
  templates exist).
- **DOCX parsing of untrusted uploads**: source files are untrusted input —
  parse with hardened libraries in jobs (resource-limited), strip/ignore
  macros, never open server-side in Office runtimes; symlink-stripping on
  zip archives.
- **Fact forgery concern** is answered by attribution, not prevention: any
  confirmed fact is attributable to a user + time + evidence; issuance
  snapshots make after-the-fact tampering detectable (hash pinning).
