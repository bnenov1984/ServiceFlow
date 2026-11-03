# Proposal — docs/02 status-model amendment (order-workflow revamp, Q1–Q5)

Status: **APPROVED by PO 26.10.2026** (with §16 dropped — Kanban is removed, Q19). Not yet applied to docs/02: the amendment lands in the same commit as the WP-G code and the P0-1 matrix tests. · Drafted: 24.10.2026
Process: docs/07 §"Change process after freeze" (rationale → impact → PO approval →
same-commit amendment of docs/02 together with the code + P0-1 tests).
Decisions: AUDIT.md §7 (PO, 24.10.2026).

## 1. Rationale

PO items #21, #22, #24, #27, #31 and the „Status-NEW" mock-up: shops want the order
screen and the status menu to guide the technician through one honest path —
intake is reviewed and *accepted* by assigning a technician, nobody works an order
without a technician, the menu shows only the next steps, going back is a deliberate
act with a reason, and „unrepairable" is a diagnostic verdict, not an escape hatch
from any status. Today the matrix allows skips out of Приета, backward moves from
the same menu as forward ones, and Неремонтируема from five statuses.

## 2. Impact assessment

| Area | Impact |
|---|---|
| docs/02 §1 | Приета displayed as „НОВА"; Предадена → Приключена drift fixed (rename of 25.09.2026 never reached docs/02). |
| docs/02 §2 | Matrix cells change (below); new rules: technician precondition, backward-with-comment, Неремонтируема only from Диагностика. |
| docs/02 §3, §4, §7, §16 | Happy path wording; exceptional flows „wrong diagnosis / additional damage / unrepairable"; part-ordered suggestion; Kanban backward drag. |
| docs/01 | Timeline: StatusChanged gains an optional `comment` (required when backward). BR-7 unchanged. No new entity. |
| docs/09 / API | Transition endpoint: `comment` field; new `message_key`s (`order.technician_required`, `order.backward_comment_required`). |
| docs/10 / UI | НОВА screen (ПРИЕМИ/ОТКАЖИ), forward-only menu, „Върни към…" action — WP-G. |
| Code | `service_orders/statuses.py` matrix + new BACKWARD set; `service.change_status` preconditions; `frontend/src/generated/transition-matrix.json` regenerated. |
| P0-1 | Exhaustive matrix tests updated in the same commit (release-blocking). |
| Data / migration | None for statuses (code `received` stays; `order_statuses` seed display name „Приета" → „НОВА" via data migration only if seed rows are per-company — verify at spec time). Legacy open orders without technician: blocked at their next working transition until assigned (accepted). |
| ADRs / C-constraints | No ADR changed. ADR-BOS-011 (common workflow for all profiles) respected. |

## 3. Proposed text (replaces the corresponding parts of docs/02)

### §1 Status Model — table rows changed

| # | Status (BG) | Kind | Purpose |
|---|---|---|---|
| 1 | НОВА *(was „Приета"; amended 24.10.2026)* | working | Intake done; waiting to be accepted by assigning a technician |
| 7 | Приключена *(was „Предадена"; renamed 25.09.2026)* | terminal-success | Customer took it; engagement complete |

### §2 Transition Matrix — new table

✔ allowed · W allowed with skip warning · ↩ backward, allowed with mandatory comment · — not allowed.

| From \ To | Диагн. | Чака кл. | Чака части | Ремонт | Готова | Приключена | Отказана | Неремонт. | Анулирана |
|---|---|---|---|---|---|---|---|---|---|
| НОВА | ✔ | — | — | — | — | — | ✔ | — | ✔ |
| Диагностика | — | ✔ | ✔ | ✔ | W | — | ✔ | ✔ | ✔ |
| Чака клиент | ↩ | — | ✔ | ✔ | W | — | ✔ | — | ✔ |
| Чака части | ↩ | ✔ | — | ✔ | W | — | ✔ | — | ✔ |
| Ремонт | ↩ | ✔ | ✔ | — | ✔ | — | — | — | ✔ |
| Готова | — | — | — | ↩ | — | ✔ | — | — | ✔ |
| terminal | — | — | — | — | — | — | — | — | — |

Rules (replacing „Backward movement is allowed…" and „Skips are allowed…"):
- **НОВА is left only by acceptance, rejection or annulment.** ПРИЕМИ assigns a
  technician (pre-filled if chosen at intake) and moves to Диагностика; ОТКАЖИ →
  Отказана; Анулирана as below. No skips out of НОВА.
- **Technician required:** entering Диагностика or any later working status
  (Ремонт, and the waiting statuses reached from them) requires an assigned
  technician; the backend rejects otherwise (`order.technician_required`).
- **Forward by default:** the status menu offers forward moves only; Чака клиент and
  Чака части are pauses and are always offered from working statuses.
- **Backward is a deliberate act** (wrong diagnosis, additional damage, failed test):
  only the ↩ cells, via a separate „Върни към…" action, mandatory comment recorded
  on the timeline with the actor. Any active user.
- **Неремонтируема only from Диагностика** — the verdict belongs to diagnosis; if
  discovered during repair, go back to Диагностика (↩, with comment) first.
- Unchanged: Приключена only from Готова; BR-7 approval/rejection when leaving Чака
  клиент; Анулирана Owner-only with reason; terminal + BR-2 unlock exception.

### §3 Happy path — changed lines

```
→ ПЕЧАТ: приемо-предавателен протокол → поръчката е НОВА
→ ПРИЕМИ (назначи техник) → Диагностика … / ОТКАЖИ → Отказана
```

### §4 Exceptional flows — changed rows

| Scenario | Handling |
|---|---|
| Repair impossible | Диагностика → Неремонтируема (if found during Ремонт: ↩ Диагностика with comment, then Неремонтируема); same fee/protocol options |
| Wrong diagnosis | ↩ Диагностика with comment; diagnosis edited in place, timeline shows the change |
| Additional damage found | ↩ Диагностика with comment, or Чака клиент (pause) with updated estimate; new approval required if estimate grew |
| Additional parts needed | → Чака части (pause, not backward); new part lines |

### §7 Parts — added sentence *(superseded by the full §7 replacement in §4 Addendum)*

When a part line is marked „поръчана" while the order is in a working status from
which Чака части is allowed, the UI suggests „Да премина ли в Чака части?" (one
click). The system never changes the status by itself. Leaving Чака части stays
manual (exit suggestion decided with the part-state review, WP-J / Q15).

### §16 Kanban — *dropped at approval (26.10.2026)*

Kanban is removed (Q19); its §16 change belongs to the removals proposal.

---

## 4. Addendum (24.10.2026, catalog decisions — AUDIT.md §8)

### §7 Parts — V1 flow *(replacement)*
Part lines are added from the catalog in Диагностика, Чака клиент, Чака части or
Ремонт — never at intake. On add the user chooses „От наличност" (издадена) or
„Поръчай" (поръчана). Marking a part поръчана suggests Чака части (one click);
when a поръчана part arrives it is marked издадена, and when no поръчана line
remains the UI suggests Ремонт. The system never changes the status by itself. Repair
may proceed before all parts arrive. No reservations, no stock in V1. Warranty is a
per-part flag (default on) with the company-wide term.

### §8 Labor *(replacement)*
Labor lines are added from the catalog: fixed-price services (qty in pieces) or
hourly items (qty in hours, e.g. 1,5 × hourly rate). Prices are never typed on the
order; corrections only via the Owner's adjustment line. Recorded by the performing
technician or the Owner.
