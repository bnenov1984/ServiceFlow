# ADR-BOS-013 — RepairFlow Price Catalog

Status: **Accepted** — approved by PO 26.10.2026, implemented
05.11.2026 (order-workflow-revamp WP-I). · Source: PO items #13, #28
(order-workflow revamp), decisions AUDIT.md §8 · Related: ADR-013
(ids/company_id), ADR-016 (tenant isolation), ADR-BOS-003 (module data
ownership), ADR-BOS-011 (profiles), docs/01 PartLine/LaborLine, OQ-5

## Context

Order lines (PartLine, LaborLine) are free text with hand-typed prices (docs/01;
discovery §5.5). The PO wants technicians to stop typing names and prices: every
line comes from a shop price list maintained by the Owner. Shops range from GSM
repair (dozens of fixed-price services) to automotive (hundreds of parts and
hourly labor), all on the common RepairFlow workflow (ADR-BOS-011).

## Decision

1. **New RepairFlow module `serviceflow.catalog`** owns one new table
   `catalog_items`; recorded in the ownership matrix (ADR-BOS-003, docs/
   business-os/05). `service_orders` reads items through the module's
   `service.py` directly — the same precedent `service_orders` already
   follows for `serviceflow.assets` (no `contracts.py` needed; a dedicated
   protected-boundary contract is reserved for edges docs/business-os/04
   rule R4 calls out specifically, e.g. the commercial ↔ service_orders
   edge). The catalog is a RepairFlow concept, not platform core —
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
   price/name field on order-line create or edit for any role. Lines may only be
   added while the order is in **Диагностика, Чака клиент, Чака части,
   Ремонт** (Q13d) — never at intake (reverses Issue 29), never on a terminal
   order (unchanged `_reject_if_terminal` rule).
5. **Maintenance:** Owner-only CRUD in Settings; CSV/Excel import (match by `code`
   when present → update, else insert; dry-run preview before commit). Items are
   **archived, never deleted** (lines reference them). *(Implementation note:
   the inline "Добави в каталога" shortcut from the line picker — Q12e —
   is UI-only convenience on top of the same Owner-only create endpoint,
   not a separate permission path.)*
6. **Corrections:** price corrections on an order are made only through the
   order-level **adjustment line** (`OrderAdjustment`: signed amount + mandatory
   reason, Owner-only — docs/01 OQ-5), which maps to the existing `adjustment`
   invoice-line source.
7. **Scope limits:** manual (non-order) invoice lines stay free text; legacy
   hand-written order lines stay as they are (`catalog_item_id` NULL). No
   inventory, stock levels, suppliers, price history or per-profile vendor seed
   catalogs.
8. **Quantity:** labor and invoice line `qty` become `numeric(10,2)` to carry
   hours (1.5). Part `qty` stays integer — a part is never hourly.

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
- *A dedicated `catalog.contracts` protected-boundary contract* (mirroring
  service_orders/commercial) — not added: the dependency is one-directional
  (`service_orders` reads `catalog`, never the reverse) and catalog has no
  cross-context write-back concern the way the commercial ↔ service_orders
  edge did (docs/business-os/04 rule R4's "first binding pair" framing).
  Revisit if a second module ever needs to read the catalog.

## Consequences

- One migration (new `catalog_items`/`order_adjustments` tables + RLS +
  `catalog_item_id`/`code` snapshot columns on `part_lines`/`labor_lines` +
  `numeric` qty on `labor_lines` and `invoice_lines` — migration 0037),
  additive-first per docs/business-os/18 §15.1(2).
- **Fractional invoice qty:** invoices carry hours as quantity (1,5 ч. × rate).
  PO decision 26.10.2026: no accountant sign-off for this change — the app is still
  pre-production with no real issued invoices.
- A shop cannot add a line the Owner has not catalogued — accepted by the PO
  (Q12e); onboarding needs the import to be usable on day one.
- New `message_key`s: `errors.catalog.*` (validation, import errors, code
  conflict), `errors.orders.lines_not_allowed_in_status` (Q13d's status gate).
- docs/01 (PartLine, LaborLine, new CatalogItem, new OrderAdjustment, OQ-5)
  and docs/02 §7/§8 amended in the same commit as the code.
- Part states (3-way `издадена`/`поръчана`/`монтирана`, #27) and the
  warranty-months-to-checkbox change (#26) are **explicitly out of scope** —
  a separate work package (WP-J); `part_lines.state`/`.warranty_days` are
  untouched by this change. *(Applied 05.11.2026 — WP-J landed both: see
  docs/01 PartLine, docs/02 §7, and migration 0038.)*

## Reconsideration triggers

- Pilot shops regularly blocked waiting for the Owner to add items → reconsider a
  technician „request item" path.
- Demand for stock levels or supplier ordering → separate inventory ADR.
