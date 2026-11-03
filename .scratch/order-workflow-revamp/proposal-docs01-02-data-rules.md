# Proposal — docs/01 + docs/02 amendment: duplicate and mileage rules

Status: **APPROVED by PO 26.10.2026** with two simplifications (app is pre-production): no prod duplicate scan, no „Възможни дубликати" list. Not yet applied: lands with the WP-B/C/D code. · Drafted: 24.10.2026
Process: docs/07 change process. Decisions: AUDIT.md §9 (Q6–Q11, Q6b, Q7b, item #20).

## Rationale

PO items #5, #6, #8, #17–#20: warnings shown *after* a record exists did not stop
duplicate customers, vehicles and parallel orders; mileage must never silently go
down; and a required mileage field blocked intake when the reading was unknown.

## Impact

docs/01 Customer + Asset (vehicle) invariants; docs/02 §3 (intake), §19 (two rows,
one new row). Reverses Cleanup Issue 26 (mileage required). No ADR change.
Service-layer checks in `customers`, `assets`, `service_orders`; new `message_key`s
(`customers.phone_taken`, `customers.eik_taken`, `assets.reg_taken`,
`orders.open_order_exists`, `orders.mileage_lower_than_previous`); new shared
normalization for reg-№ homoglyphs (+ re-normalization of stored identifiers).
Legal review of the lower-mileage flag
wording before release.

## Proposed text

### docs/01 Customer — Lifecycle *(amended 24.10.2026)*
created → active → archived. An **individual** cannot be created (or have its phone
changed) to a normalized phone that another non-anonymized individual already has;
the user is offered the existing customer instead. A **company** cannot be created
(or have its ЕИК changed) to an ЕИК another company already has. Phones shared
between an individual and a company are allowed.

### docs/01 Asset (vehicle) — Invariants *(added 24.10.2026)*
VIN and registration № are each unique per company when present (normalized:
uppercase alphanumerics, Cyrillic/Latin look-alike letters folded). Mileage on an
order is optional; when entered it must be ≥ the highest mileage recorded for the
asset, unless the Owner confirms a lower reading — then the reading is stored as
read, flagged „по-малък от предишния — потвърдено", with a mandatory timeline
comment. Mileage is never overwritten with a different value than the one read.

### docs/02 §3 — intake line *(changed)*
→ Регистрирай/избери актив (при съществуващ: последни посещения + последен пробег;
отворена поръчка → блок с връзка към нея) → Създай поръчка …

### docs/02 §19 — rows *(changed / added)*

| Scenario | Mitigation |
|---|---|
| Duplicate customer | Individuals: normalized phone unique — blocked inline with „Избери съществуващия"; companies: ЕИК unique — blocked inline |
| Duplicate vehicle | VIN and рег. № unique per company — blocked inline with „Избери този автомобил" |
| Duplicate order | Same asset + open order (any non-terminal status, incl. Готова) **blocked** at the asset step and on create; link to the open order |
| Mileage lower than before | Blocked; Owner-only confirmation stores the real reading with a flag + comment |
