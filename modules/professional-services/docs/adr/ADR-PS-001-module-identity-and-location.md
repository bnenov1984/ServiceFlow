# ADR-PS-001 — Module identity, name, and location

Status: **Proposed** · Date: 18.07.2026

## Context

The commission provisioned name "Professional Services", id
`professional-services`, path `C:\Projects\BusinessOS\modules\professional-services`,
and required verification against repository conventions before permanent use.

Verified reality: the Business OS repository is the existing ServiceFlow
repository that currently hosts the Business OS module documentation — the
current repository root, verified by inspection (no repo exists at the
commissioned path; the outer Windows directory name is not architecturally
authoritative, and a future repository rename or relocation is optional and
mechanical); the established module convention is
`modules/<kebab-slug>/` with a domain-descriptive slug — precedent:
`modules/construction-supervision` (module #2, docs-only). BOS-06 fixes the
module id as a lowercase slug doubling as table-name and i18n namespace
prefix. Product *brands* in the platform's vision use the "*Flow" family
(ServiceFlow, InvoiceFlow…), distinct from module ids.

Alternatives considered: `practice-management` (industry-standard category
term, but an Anglicism opaque to the Bulgarian buyer and no more precise);
`engagements` / `assignments` (name the object, not the vertical — the
platform names modules by domain served); `caseflow` (a brand, not a module
id; branding is Q-1 in PS-36, a PO marketing decision that must not leak
into technical identifiers).

## Decision

- Module id: **`professional-services`** — consistent with the
  domain-descriptive precedent; the commissioned name survives verification.
- Python package: `professional_services`; table prefix **`ps_`** (the full
  id is impractically long for 22 table names; the short prefix is declared
  here and in BOS-06 `tables`); i18n namespace `ps.`.
- Location: **`modules/professional-services/`** in the actual repository —
  the commissioned *relative* location under the verified root.
- Working product name: "Professional Services" / „Професионални услуги";
  brand naming stays open (PS-36 Q-1) and never changes the id.

## Consequences

- Parallel and symmetrical to `construction-supervision`; no new convention.
- The `ps_` prefix must stay collision-free platform-wide (no other module
  claims it; checked — none does).
- If the PO later brands the product, marketing name ≠ id, exactly as
  ServiceFlow's id `serviceflow` would survive a rebrand.
