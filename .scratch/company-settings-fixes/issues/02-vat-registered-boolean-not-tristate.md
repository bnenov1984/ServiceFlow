# `vat_registered` is still a tri-state (Yes/No/NULL), not a real boolean

Status: done (2026-09-26)

## Implementation notes

Went with option 2 (UI-only fix, no migration), confirmed correct by reading
`customers/service.py` first as instructed: `_validate_vat_identity`'s own
docstring says "UNKNOWN and explicitly-not-registered are both valid,
complete states on their own", `anonymize()` deliberately resets
`vat_registered` to `None` as part of GDPR erasure, and
`_derive_bg_vat_number`/`_validate_vat_identity` both treat `None` as a real,
needed "not yet known" state distinct from `False`. Backend
(`Customer.vat_registered: bool | None`, contracts, router, service) is
**unchanged** — this was purely a frontend fix.

`CustomerCompanyFields.tsx`'s VAT-status control (shared by
`NewCustomerForm`/`CustomerStep` at create and
`CustomerCompanyDetailsSection` at edit) had three buttons: "Не е
проверено" (unknown) / "Не" / "Да". Removed the unknown button entirely —
only Да/Не remain. `null` is still a legitimate value (neither button shows
`aria-pressed`), reachable only as the pre-first-choice default (new
customer, VAT status never touched) or already-`null` on an existing
record — never by clicking anything. The amber "Докато ДДС статусът не
бъде потвърден…" hint (still real, accurate information tied to the
backend's invoicing block) stays exactly as before, still shown only when
the value is `null`. Read-only display of the three labels
(`vatStatusLabel` in `CustomerCompanyDetailsSection.tsx`) is unchanged —
that's a status label, not a selectable control, and displaying "Не е
проверено" for an existing unconfirmed customer is correct information, not
the tri-state choice the PO objected to.

Updated the three test assertions elsewhere that had been clicking/checking
the now-removed button (`CustomerCompanyDetailsSection.test.tsx` ×2,
`CustomerStep.test.tsx` ×1) to instead assert its absence.

Verified: frontend vitest (523 passed total), `tsc --noEmit` clean. No
backend changes, so no backend re-run was needed for this issue specifically
(covered by the full-suite run done alongside issue 01).

## Context

PO's original ask (item 10): no "not verified" tri-state for VAT
registration — only Yes/No. Confirmed still unfixed:
`backend/src/serviceflow/customers/models.py:31`:
`vat_registered: Mapped[bool | None] = mapped_column(default=None)`.
`customers/contracts.py:32` and the router propagate the same `bool | None`
end to end.

## Why it's `bool | None` today (check before changing)

`backend/tests/test_migration_0018_tax_event_date.py` /
`test_isolation.py`-adjacent history and `1280333`'s commit message
("two customer tests now omit eik so vat_number rejection is still
reachable after Wave 5 added auto-derivation from eik") suggest
`vat_registered` may be auto-derived from `eik` (Bulstat) length in some
code path (`customers/service.py`). **Read that derivation logic first** —
this field probably went nullable specifically to represent "not yet known
until an EIK is entered," which is a real state, just not one the PO wants
surfaced as a third UI option.

## Scope

Two ways to resolve, pick based on what the derivation logic actually needs:

1. If nothing legitimately needs a `NULL` state: make the column
   `Mapped[bool]` with a `default=False`, migration to backfill existing
   NULLs to `False`, and drop the nullable Pydantic/UI paths.
2. If `NULL` genuinely means "not yet derivable" (e.g. no `eik` entered
   yet) and that's a real, needed backend state: keep the column nullable,
   but fix the **UI** so the customer-facing form never presents "Не е
   проверено" as a choice — only Да/Не — and NULL is purely an internal
   default before first save, never user-selectable.

Given the PO's complaint is specifically about a UI tri-state choice, (2)
is likely sufficient and lower-risk (no migration, no backend behavior
change) — but verify the derivation logic doesn't actually depend on a
tri-state UI before assuming.

## Acceptance criteria

- `uv run pytest` green (adjust `test_customers.py` if the nullable
  contract changes).
- Manual/E2E check: the VAT field in the customer form only ever shows two
  options.
