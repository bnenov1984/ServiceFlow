# Part-level warranty: days → months

Status: done (2026-09-26)

## Context

`PartLine.warranty_days` (migration `0025`) is currently day-granularity,
input/output as days end to end (`service_orders/router.py`,
`protocol.py`'s `_warranty_text`). PO's example used whole months (12
months, 6 months) and explicitly asked for a "Гаранция: ___ месеца" field
per part line.

## Open technical decision

Two ways to satisfy "months" as the unit without losing precision or
breaking the existing `warranty_days`-based warranty-return logic
(`service_orders/service.py`'s `warranty_return`, which presumably compares
elapsed days against `warranty_days`):

1. **Keep `warranty_days` as the stored/compared value**, make the
   UI/API-facing field months-only (integer months, converted ×30 — or
   ×`30.44` — to days on write, ÷30 on read for display). Simplest, no
   migration, but loses exact day precision and "30 days" vs "1 month" can
   drift.
2. **Add a real `warranty_months` column**, migrate existing `warranty_days`
   values (round to nearest month), and make warranty-return date math work
   in months instead of days.

Recommend (1) unless `warranty_return`'s date math turns out to already be
fragile — check `service_orders/service.py`'s `warranty_return` and
`_warranty_text` before deciding, and confirm with the PO if (2) turns out
necessary (real schema/semantics change, not just a UI relabel).

## Scope

- Apply the chosen conversion in `PartLinesSection.tsx` (or its replacement
  from `unified-order-lines/issues/01`, if that lands first — check for
  conflicts) and `service_orders/router.py`'s Pydantic models.
- Update `protocol.py`'s `_warranty_text` to render "N месеца" instead of
  "N дни".
- Company-level `parts_days` default (issue 04) needs the same
  days↔months handling at the point it seeds a new part line's default.

## Acceptance criteria

- Existing `warranty_days`-based tests updated, not deleted (rename/adjust
  assertions to months where user-facing, keep backend precision correct).
- `uv run pytest` green.

## Implementation notes

**Decision confirmed as option (1)**: checked `warranty_return` first, as
instructed — it does no date math at all (just checks
`kind_of(status) == TERMINAL_SUCCESS` and opens a linked follow-up order),
so there was never a fragility risk to weigh against a migration. No
schema change, no PO consultation needed.

**Boundary, not storage, changed**: `PartLine.warranty_days` (DB column,
`service_orders/lines.py`, `warranty_return`, the frozen
`completion_snapshot`) is untouched — still day-granularity throughout the
service layer. Only `service_orders/router.py`'s `PartLineIn`/
`PartLinePatch`/`PartLineOut` and the frontend's `PartLinesSection.tsx`
work in months, via new `_days_to_months`/`_months_to_days` router helpers
(30 days/month exactly, round-trips the PO's own 12/6-month examples
without drift). `patch_part_line` translates `warranty_months` →
`warranty_days` in the dict before it reaches `lines.update_part_line`'s
generic `setattr()` — that function writes whatever keys it's given
straight onto the ORM model, so a raw `warranty_months` key would have
silently done nothing.

**Order-level (labor) warranty is explicitly untouched** — stays days
end to end (`OrderPatch`/`StatusChange`/`OrderOut`/`CompletionDialog`'s
"Гаранция (дни)" field, `protocol.py`'s `_warranty_text`). Only added a
sibling `_warranty_text_months` for part-line rendering — same NULL/0
semantics, plus correct Bulgarian singular ("1 месец" vs "N месеца").

**Company `parts_days` default stays in days too** (company-settings
screen, unchanged) — `PartLinesSection.tsx` converts it to months only at
the point it prefills the new-part-line input, the one place a
days-shaped value meets this months-shaped field.

Verified: backend 772 passed (+1) + 2 xfailed (unchanged, pre-existing +
issue-04's), frontend 522 passed, `ruff`/`mypy`/`lint-imports`/
`tsc --noEmit` all clean.
