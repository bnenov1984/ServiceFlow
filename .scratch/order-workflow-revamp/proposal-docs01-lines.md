# Proposal — docs/01 amendment: order lines, catalog, adjustment, part warranty

Status: **APPROVED by PO 26.10.2026.** Not yet applied to docs/01: lands in the same commit as the catalog/lines code. · Drafted: 24.10.2026
Process: docs/07 change process. Decisions: AUDIT.md §8. Companion: proposal-ADR-catalog.md.

## Rationale

PO items #13, #26, #27, #28: lines come from an Owner-maintained price list,
parts get three line states, the part warranty becomes a yes/no flag with a
company-wide term, and corrections go through one adjustment line.

## Impact

docs/01 entity sections (PartLine, LaborLine, new CatalogItem, new
OrderAdjustment), aggregate list (§4), OQ-5 status; docs/02 §7/§8 (see the
status-model proposal); docs/08/09 at spec time. Fixes pre-existing drift:
docs/01 still lists the 4 pre-Issue-33 part states.

## Proposed text

### PartLine *(amended 24.10.2026)*
- **Purpose:** a physical component used in this repair. Lightweight — no inventory,
  no reservations (discovery S5).
- **Attributes:** catalog item reference (0..1; NULL on legacy lines), snapshot of
  name, code, unit cost and unit price taken from the catalog at add-time,
  quantity, state: **издадена** (from the shop's own supply) · **поръчана**
  (must be ordered) · **монтирана**, warranty flag (default on; term from
  company settings; legacy lines keep their stored months).
- **Lifecycle:** added only in Диагностика, Чака клиент, Чака части, Ремонт. Added
  as издадена or поръчана; поръчана → издадена when it arrives → монтирана.
- **Invariants:** belongs to exactly one order; created only from a catalog item
  (no free text, no hand-typed price); later catalog changes never alter it (BR-3).

### LaborLine *(amended 24.10.2026)*
- **Purpose:** work performed, priced from the catalog — per operation (unit бр.) or
  per hour (unit час).
- **Attributes:** catalog item reference (0..1), snapshot of description, unit and
  unit price, quantity (decimal; hours for hourly items), optional duration info,
  performed by (0..1).
- **Invariants:** as PartLine — catalog-only creation, same allowed statuses, snapshot
  never re-priced.

### CatalogItem *(new)*
- **Purpose:** one entry of the shop's price list (part or labor).
- **Attributes:** kind (част/труд), name, code (optional, unique per company), unit
  (бр./час), sale price (net), unit cost (optional, Owner-only), archived flag.
- **Lifecycle:** Owner creates/edits/imports/archives; never deleted.
- **Owner module:** `serviceflow.catalog` (ADR-BOS-013).

### OrderAdjustment *(new — resolves OQ-5)*
- **Purpose:** the only way to correct an order's price („направи го 50 €").
- **Attributes:** signed amount, mandatory reason, created by (Owner).
- **Invariants:** Owner-only; feeds derived totals (BR-3); becomes an `adjustment`
  invoice line in the draft; timeline-logged.

### §4 aggregate list
ServiceOrder aggregate gains OrderAdjustment. CatalogItem is **outside** the
ServiceOrder aggregate (referenced, snapshotted).

### Open questions
- OQ-5 → **Resolved 24.10.2026**: order-level adjustment line, Owner-only.

