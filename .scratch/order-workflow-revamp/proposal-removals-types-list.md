# Proposal — removals, per-profile asset types, list-only orders

Status: **APPROVED by PO 26.10.2026** with a simplification (app is pre-production): tasks tables dropped in the same change, old asset types replaced outright (non-fitting test assets may be deleted). Not yet applied: lands with the WP-C/H/K code. · Drafted: 24.10.2026
Process: docs/07 change process. Decisions: AUDIT.md §10 (Q16–Q19 incl. b/c).

## Rationale

PO items #1, #7, #9, #25, #29b: automotive shops do not log accessories; tasks are
noise next to the new status-driven order screen; a profile already implies the
asset type, so the picker is an extra step; and the Kanban board duplicates every
new status rule (ПРИЕМИ dialog, backward comment, server blocks) on a second surface.

## Impact

| Area | Change |
|---|---|
| docs/01 | Task entity → **Retired 24.10.2026** (history kept in timeline); AccessoryItem: recorded only for asset types with accessories enabled; BR-9 scoped accordingly. |
| docs/02 | §3 intake (no type picker, accessories conditional, no tasks); §5 Tasks → retired; §15 dashboard four widgets; §16 Kanban → retired, replaced by the orders table. Also drops the §4 „auto-created call task" and the §19 „Call task" mitigation. |
| ADR-BOS-011 | §4 a profile seeds exactly one asset type; §5 seeding per profile; §8 accessories move from „common" to an asset-type property (`accessories` flag next to `field_defs`). |
| docs/business-os/18 | §15.1(1) „identical asset types for all profiles" → superseded. |
| Code | Remove `TasksChecklist`, task dashboard counts, call-task job, `KanbanBoard`/`OrderCard` drag path, intake type picker; new `asset_types.accessories` flag; seed new types; orders table. |
| Data / migration | New asset-type rows per tenant + `accessories` column; old asset types replaced outright; tasks tables dropped in the same change. Accessory tables stay (still used by non-vehicle types). |
| Tests | Task tests (incl. P0 isolation) removed with the tables; Kanban tests removed with the board. |

## Proposed text

### docs/01 Task *(Retired 24.10.2026)*
Tasks are no longer part of RepairFlow. Existing task events remain in order
timelines (append-only). The „customer not collecting" reminder is the dashboard's
„Готови от над N работни дни" highlight, derived from status age.

### docs/01 AccessoryItem + BR-9 *(amended 24.10.2026)*
Recorded at intake only when the order's asset type has accessories enabled
(Автомобил: disabled). BR-9 applies to orders that have accessory items.
Accessories already recorded keep printing on protocols and snapshots.

### docs/02 §15 Dashboard *(replacement)*
Four operational widgets, each opening the filtered orders table: Активни поръчки ·
Чака части · Готови за получаване (with „над 5 работни дни" highlight) · Просрочени.
No charts, no vanity metrics.

### docs/02 §16 Orders list *(replaces Kanban)*
One table of orders: № · Статус · Клиент · Актив · Техник · Дни в статуса · Обещана
дата. Status chips („Всички отворени" + each open status) and filters: technician,
priority, overdue. Default order: overdue first, then longest in status. On phones
the same data as stacked cards. The list does not change statuses; that happens
only on the order page.

### ADR-BOS-011 *(Amended 24.10.2026)*
- §4: a profile seeds **exactly one** asset type, so intake shows no type picker.
  An asset type carries `field_defs` and an `accessories` flag.
- §5: seed map: automotive_repair → Автомобил (accessories off) · phone_repair →
  Телефон / таблет (+ „вид") · electronics_repair → Устройство · appliance_repair →
  Уред · generic_repair → Друго (accessories on for all but Автомобил). Existing
  tenants: old types replaced by the profile's type.
- §8: „accessories" removed from the always-common list; it is an asset-type
  property. Workflow, matrix, diagnosis, parts/labor, protocol and invoicing stay
  common.
