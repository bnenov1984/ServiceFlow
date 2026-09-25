# Company name not editable after signup

Status: done (2026-09-26)

## Implementation notes

`name` added to `CompanyRequisitesPatch`/`CompanyRequisitesOut`
(`business_os/identity/router.py`), `Field(min_length=1, max_length=200)` so
a blank name is rejected outright (422 → `errors.validation`) rather than
silently applied. Unlike `address`/`phone`/`eik`, `name` is a real `Company`
column, not a `requisites` JSONB key, so
`identity/service.py::update_company_requisites` writes it directly
(same pattern already used for `vat_registered`) and it's excluded from
`COMPANY_REQUISITE_KEYS`. Frontend: new `company-name` input in
`CompanyRequisitesPage.tsx`, above Адрес, owner-gated the same as the rest
of the form; new i18n key `company.field_name`.

Checked downstream effects per the issue's own suggestion: no
`search/service.py` exists in this codebase (nothing to check there); every
consumer of `Company.name` (`protocol.py`'s intake PDF,
`commercial/service.py`'s invoice seller snapshot, `identity/contracts.py`'s
`CompanyProfile`) reads it live from the DB at use time, so a rename has no
caching/staleness concern.

Regenerated `frontend/src/generated/openapi.json` + `api.d.ts`
(`scripts/export_openapi.py` + `npm run gen:api`) since the contract shape
changed.

Verified: `test_company_requisites.py` (22 passed, new `test_owner_can_
change_name` + `test_blank_name_is_rejected`), full backend suite, frontend
vitest (523 passed, +1 new test), `tsc --noEmit`/`ruff`/`mypy`/`lint-imports`
all clean.

## Context

`frontend/src/vendor/VendorNewCompanyPage.tsx` (signup) has a real
company-name input saved to `Company.name`
(`backend/src/business_os/identity/models.py:34`). But
`frontend/src/settings/CompanyRequisitesPage.tsx` (the post-signup company
settings screen) only exposes `address`, `phone`, `eik`, `vat_registered`
— there is no field to edit the company's own name once it's set. If a
shop's legal name changes, or was entered wrong at signup, there's no way
to fix it without vendor/admin intervention.

## Scope

- Add a `name` field to `CompanyRequisitesPage.tsx`, owner-editable (same
  gating as the rest of that page).
- Backend: confirm `PATCH /company` (or whichever endpoint
  `CompanyRequisitesPage.tsx` calls) accepts a `name` field — extend the
  Pydantic contract + `identity/service.py` update path if it doesn't.
- Consider whether renaming a company needs any downstream effects (e.g.
  invoice header re-render, search index — check `search/service.py`'s use
  of company name) — likely fine since invoices/PDFs pull live data, but
  verify rather than assume.

## Acceptance criteria

- Backend test: PATCH updates `Company.name`.
- Frontend test: field renders, saves, respects existing owner-only gate.
