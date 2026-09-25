# Free-text company warranty terms in settings

Status: done (2026-09-25)

## Context

`business_os/identity/service.py` already stores
`company.settings.repairflow.warranty_defaults = {labor_days, parts_days}`
— numeric only. PO wants this expanded to real terms text, and wants it
seeded at onboarding (by Vendor/Admin) rather than left blank for the Owner
to fill in later.

PO's field list (their wording):
- standard warranty term ("стандартен гаранционен срок")
- warranty conditions ("гаранционни условия")
- warranty text ("текст на гаранцията")
- additional conditions ("допълнителни условия")

Note for the PO: this expands who can set warranty terms beyond the
Owner-only rule stated earlier in the audit — Vendor/Admin now seeds initial
values at company onboarding, Owner edits afterward. Confirmed by PO
2026-09-25; flagging here for anyone auditing this decision later since it
reads as a reversal of the original "Vendor should never set commercial
terms" principle.

## Scope

- Extend `company.settings.repairflow.warranty_defaults` (or a new
  sub-key, e.g. `warranty_terms`) with the four free-text fields above,
  alongside the existing `labor_days`/`parts_days` numeric defaults (do not
  remove those — issue 05 still needs `parts_days`-equivalent, see below).
- Onboarding flow (wherever Vendor/Admin provisions a new company —
  `business_os/platform_admin/` or `VendorNewCompanyPage.tsx`'s backend
  counterpart) gets fields to set initial warranty terms.
- `frontend/src/settings/CompanyRequisitesPage.tsx`'s `WarrantyDefaultsSection`:
  add the four text fields, still gated to `me?.is_owner` for post-onboarding
  edits.
- Access control: confirm/adjust `company_router`'s `require_owner`
  dependency — Vendor-side onboarding writes go through a *different*
  router (platform_admin, vendor-authenticated), not through the
  owner-gated tenant router, so no relaxation of `require_owner` should be
  needed. Verify this rather than assuming.
- Protocol document (`service_orders/protocol.py`) should be able to pull
  and render these terms — coordinate with issue 03's warranty-email
  variant.

## Acceptance criteria

- New/updated backend tests (extend `test_warranty_defaults.py` and
  `test_warranty_defaults_fallback.py`).
- i18n keys for all new field labels (no literal strings, root `CLAUDE.md`
  rule 4).
- `uv run pytest`, `tsc --noEmit` clean.

## Implementation notes

**Shape**: kept one sub-key, `company.settings.repairflow.warranty_defaults`
(not a new `warranty_terms` sibling) — `standard_term`/`conditions`/`text`/
`additional_conditions` extend `WARRANTY_DEFAULT_KEYS` alongside the
existing `labor_days`/`parts_days`, one PATCH/GET pair
(`/company/warranty-defaults`), one form section. `WarrantyDefaultsOut` now
always returns all six keys.

**Non-committing write path added**: `identity.service._set_warranty_defaults`
(extracted from `update_warranty_defaults`, which still audits+commits for
the tenant-facing endpoint) is composed into `platform_admin.service.
provision_company`'s single transaction via the new
`identity.contracts.set_warranty_defaults` — mirrors `set_business_profile`'s
established non-committing-contract-function pattern exactly. Onboarding
fields are entirely optional; an all-blank form writes nothing (no stray
empty-string overrides).

**`require_owner` confirmed unchanged** — `company_router` still gates
every post-onboarding edit; the onboarding write goes through
`platform_admin`'s vendor-authenticated router, a structurally separate
path, exactly as the issue anticipated.

**Protocol wiring**: company terms are frozen into `completion_snapshot`
at completion time (same reproducibility discipline as every other
snapshot field — a later terms edit never retroactively changes an
already-printed/emailed protocol) and render in a new "Гаранционни
условия" section, gated by issue 03's `include_warranty` flag exactly like
the per-part/labor warranty lines. Old snapshots (pre-issue-04) default the
four fields to `""` rather than KeyError.

**Pre-existing P0 bug hit, not introduced**: the new section's rendering
uses `multi_cell`, same as the existing "Диагноза" section — which already
has a tracked, `xfail(strict=True)` P0 bug
(`test_delivery_protocol_renders_after_delivery`,
`fpdf.errors.FPDFException: Not enough horizontal space to render a single
character`). Two new tests that set enough company-terms text to trigger it
are marked `xfail(strict=True)` with the same reasoning, not worked around
— hand-rolling a manual PDF word-wrapper to dodge a tracked library bug
would be its own unscoped, risky side project. When that P0 is eventually
fixed, both the diagnosis section and this one should start working
together (`strict=True` will catch it either way).

Verified: backend 771 passed (+10) + 2 xfailed (1 pre-existing + 1 new,
same root cause), frontend 522 passed (+4), `ruff`/`mypy`/`lint-imports`/
`tsc --noEmit` all clean.
