# ADR-BOS-013 — RepairFlow Price Catalog

Status: **APPROVED by PO 26.10.2026** — moves to docs/adr/ in the same commit as
the catalog code. · Source: PO items #13, #28 (order-workflow revamp),
decisions AUDIT.md §8 · Related: ADR-013 (ids/company_id), ADR-016 (tenant
isolation), ADR-BOS-003 (module data ownership), ADR-BOS-011 (profiles), docs/01
PartLine/LaborLine, OQ-5

## Context

Order lines (PartLine, LaborLine) are free text with hand-typed prices (docs/01;
discovery §5.5). The PO wants technicians to stop typing names and prices: every
line comes from a shop price list maintained by the Owner. Shops range from GSM
repair (dozens of fixed-price services) to automotive (hundreds of parts and
hourly labor), all on the common RepairFlow workflow (ADR-BOS-011).

## Decision

1. **New RepairFlow module `serviceflow.catalog`** owns one new table
   `catalog_items`; recorded in the ownership matrix (ADR-BOS-003).
   `service_orders` reads items through the module's public contract only; it never
   writes catalog tables. The catalog is a RepairFlow concept, not platform core —
   `business_os.*` does not know it.
2. **Item shape (flat, no categories/variants):** `id` (UUIDv7), `company_id`,
   `kind` (`part` | `labor`), `name`, `code` (optional, unique per company when
   set), `unit` (`pcs` | `hour`), `sale_price` (numeric, **net**), `unit_cost`
   (numeric, optional, Owner-only visibility), `archived_at` (nullable). Hourly
   labor = `kind=labor, unit=hour`; fixed services = `kind=labor, unit=pcs`.
3. **Tenant isolation:** RLS `FORCE` + fail-closed GUC policy, scoped chokepoint
   for all queries, isolation tests added to the P0-9 set.
4. **Strict lines:** new order lines are created only from a catalog item. The line
   **snapshots** name, code, unit, sale price and unit cost at add-time and keeps
   a nullable `catalog_item_id` reference (BR-3: totals derived from the line's own
   snapshot; later catalog price changes never touch existing lines). No
   price/name field on order-line create or edit for any role.
5. **Maintenance:** Owner-only CRUD in Settings; Excel/CSV import (match by `code`
   when present → update, else insert; dry-run preview before commit); inline
   „Добави в каталога" from the line picker, Owner-only. Items are **archived,
   never deleted** (lines reference them).
6. **Corrections:** price corrections on an order are made only through the
   order-level **adjustment line** (signed amount + mandatory reason, Owner-only —
   docs/01 OQ-5), which maps to the existing `adjustment` invoice-line source.
7. **Scope limits:** manual (non-order) invoice lines stay free text; legacy
   hand-written order lines stay as they are (`catalog_item_id` NULL). No
   inventory, stock levels, suppliers, price history or per-profile vendor seed
   catalogs.
8. **Quantity:** labor and invoice line `qty` become `numeric(10,2)` to carry
   hours (1.5). Part `qty` stays integer in the UI.

## Alternatives considered

- *Catalog as suggestion, fields stay editable* — rejected by PO (Q12a): does not
  stop hand-typed prices.
- *Owner price override per line* — rejected (Q12a); the adjustment line covers
  the real need without per-line overrides.
- *Vendor-seeded catalogs per profile* — rejected (Q12b): prices are per shop; a
  single maintainer cannot curate them.
- *Merging PartLine/LaborLine into one table* — not needed; the catalog `kind`
  drives a combined UI list while the two line tables stay (unified-order-lines
  design intent).
- *Inventory module* — out of scope (docs/01 „no inventory in V1"; Q15).

## Consequences

- One migration (new table + RLS + `catalog_item_id` and snapshot columns on line
  tables + `numeric` qty on `labor_lines` and `invoice_lines`), additive-first per
  docs/business-os/18 §15.1(2).
- **Fractional invoice qty:** invoices carry hours as quantity (1,5 ч. × rate).
  PO decision 26.10.2026: no accountant sign-off for this change — the app is still
  pre-production with no real issued invoices.
- A shop cannot add a line the Owner has not catalogued — accepted by the PO
  (Q12e); onboarding needs the import to be usable on day one.
- New `message_key`s: catalog validation, import errors, `order.line_requires_catalog_item`,
  `order.lines_not_allowed_in_status`.
- docs/01 (PartLine, LaborLine, new CatalogItem, OQ-5) and docs/02 §7/§8 amended in
  the same commit as the code.

## Reconsideration triggers

- Pilot shops regularly blocked waiting for the Owner to add items → reconsider a
  technician „request item" path.
- Demand for stock levels or supplier ordering → separate inventory ADR.
