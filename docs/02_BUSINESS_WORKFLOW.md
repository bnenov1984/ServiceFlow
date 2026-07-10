# 02 — Business Workflow

Status: **Approved by Product Owner 10.07.2026 — all open questions (OQ-W1…OQ-W4) accepted with proposed defaults** · Date: 10.07.2026
Input: Blueprint Part 4 + Discovery decisions (00) + Domain Model (01)
Business document: how the shop works and how the software supports it. No technology.

---

## 1. Status Model (approved simplified model)

Seven working statuses + four terminal outcomes + archive flag. Internal semantic
kinds are fixed; Bulgarian display names are what users see.

| # | Status (BG) | Kind | Purpose — the question it answers |
|---|-------------|------|-----------------------------------|
| 1 | Приета | working | Intake done; nobody has looked at it yet |
| 2 | Диагностика | working | A technician is evaluating it |
| 3 | Чака клиент | waiting | Estimate given; customer must decide |
| 4 | Чака части | waiting | Approved; blocked on parts |
| 5 | Ремонт | working | Actively being repaired |
| 6 | Тестване | working, **toggleable per company** | Verifying the repair |
| 7 | Готова | ready | Done; waiting for pickup |
| 8 | Предадена | terminal-success | Customer took it; engagement complete |
| 9 | Отказана | terminal-failure | Customer declined the estimate |
| 10 | Неремонтируема | terminal-failure | Cannot / not worth repairing |
| 11 | Анулирана | terminal-failure | Created by mistake / duplicate |

**Архивирана is a flag, not a status** — applies to any terminal order; hides it from
operational views; reversible by Owner.

## 2. Transition Matrix

Rows = from, columns = to. ✔ allowed · W = allowed with warning (skip) · — not allowed.
All transitions require an authenticated user; backend always validates (Kanban is
just one way to trigger them).

| From \ To | Диагн. | Чака кл. | Чака части | Ремонт | Тестване | Готова | Предадена | Отказана | Неремонт. | Анулирана |
|---|---|---|---|---|---|---|---|---|---|---|
| Приета | ✔ | W | W | W | W | W | — | ✔ | ✔ | ✔ |
| Диагностика | — | ✔ | ✔ | ✔ | W | W | — | ✔ | ✔ | ✔ |
| Чака клиент | ✔ | — | ✔ | ✔ | W | W | — | ✔ | ✔ | ✔ |
| Чака части | ✔ | ✔ | — | ✔ | W | W | — | ✔ | ✔ | ✔ |
| Ремонт | ✔ | ✔ | ✔ | — | ✔ | ✔ | — | — | ✔ | ✔ |
| Тестване | ✔ | ✔ | ✔ | ✔ | — | ✔ | — | — | ✔ | ✔ |
| Готова | — | — | — | ✔ | ✔ | — | ✔ | — | — | ✔ |
| terminal | — | — | — | — | — | — | — | — | — | — |

Rules encoded above:
- **Предадена only from Готова** (you can't hand over what isn't ready). Delivery
  prompts: accessories return check, warranty days, payment settlement, optional
  invoice, protocol print.
- **Backward movement is allowed** among working statuses (wrong diagnosis, additional
  damage, failed test) — always timeline-logged with the actor.
- **Skips are allowed with a warning** (small shops legitimately jump Приета → Ремонт
  for trivial jobs). The warning keeps the honest path visible without blocking
  reality.
- **Чака клиент exit to a forward status requires a recorded approval** (BR-7);
  exit to Отказана requires a recorded rejection.
- **Анулирана** (mistake) is Owner-only and requires a reason.
- Terminal statuses accept no further transitions; only payments settling balance,
  protocol printing and archiving remain possible.

Timeline events per transition: StatusChanged + specific events (EstimateApproved,
OrderReady, OrderDelivered…) per 01 §5. Notifications: none in V1 (V1.5 hooks noted).
Permissions: any active user may perform allowed transitions except Анулирана
(Owner-only); see §12 role matrix.

## 3. Main Workflow (refined happy path)

```
Клиент идва → Намери/създай клиент (търсене по телефон, предупреждение за дубликат)
→ Регистрирай/избери актив → Създай поръчка №2026-00042:
     оплакване (задълж.) · аксесоари чеклист · снимки при приемане (препор.)
     · обещана дата · приоритет · техник (по избор)
→ ПЕЧАТ: приемо-предавателен протокол (A4) — клиентът си тръгва с него
→ Диагностика: находка, причина, препоръка, оценка (цена/срок), нужда от одобрение?
   ├─ одобрение нужно → Чака клиент → обаждане → запис на одобрение/отказ
   └─ не → продължава
→ Части нужни? → редове „части“ (needed→ordered→received) → Чака части при блокаж
→ Ремонт → (Тестване, ако е включено) → Готова
→ Клиентът идва: аксесоари върнати ✓ · плащане(ия) · [фактура по желание]
   · гаранционен срок · ПЕЧАТ: протокол за предаване → Предадена
→ (по-късно) Архивирана
```

Target times (success metrics): intake incl. protocol ≤ 2 min for existing customer,
≤ 3 min for new; delivery incl. payment ≤ 1 min; invoice generation ≤ 1 min.

## 4. Exceptional Flows (from the blueprint, mapped)

| Scenario | Handling |
|----------|----------|
| Customer rejects estimate | Чака клиент → Отказана (reason recorded); diagnostic fee invoiceable + payable on the terminal order; delivery of unrepaired asset via protocol print from Отказана |
| Repair impossible | → Неремонтируема; same fee/protocol options |
| Customer never returns | Готова + N days → dashboard warning + auto-created call task; remains Готова until delivered or Owner archives with note (no extra status) |
| Wrong diagnosis | Back to Диагностика; diagnosis edited in place, timeline shows the change |
| Additional damage found | Back to Диагностика or Чака клиент with updated estimate; new approval required if estimate grew |
| Additional parts needed | Back to Чака части; new part lines |
| Invoice correction | Issued invoice → Annul (reason) → new Draft → Issue (new number, references annulled one) |
| Warranty return | New order linked to original; badge „Гаранционна“; original stays terminal |

## 5. Tasks — rules

Created by anyone at any time (typical: during diagnosis and repair). Assignable,
reassignable, reopenable while the order is non-terminal. **Not mandatory** — trivial
repairs need zero tasks. **Completion never auto-changes order status** (V1: humans
move orders; revisit only if pilot data shows friction). Call-flagged tasks feed the
dashboard's „Обади се на клиента“ widget. Company-level tasks (no order) allowed for
shop chores.

## 6. Diagnosis & Customer Approval

Diagnosis answers: what's wrong · why · repairable? · cost · duration. One record,
edited in place, every edit timeline-logged. Approval model V1 (simplest operational,
per discovery S3): the shop calls/talks; a user records the outcome — who, when,
channel (телефон / на място / съобщение), and what was approved (amount). No customer
portal, no tokens, no SMS in V1. The recorded approval is the shop's operational
evidence, not a legal signature (protocol carries signatures).

## 7. Parts — V1 flow

Anyone may add part lines during diagnosis/repair; states: **needed → ordered →
received → installed** (+ removed). „Чака части" is used when the order is blocked;
part receipt is recorded by whoever unpacks the delivery. Repair may proceed before
all parts arrive (partial work is real). No reservations, no stock, no returns-to-
inventory in V1 (no inventory exists); unused part lines are removed with timeline
trace.

## 8. Labor

Fixed-price lines (description × qty × unit price), matching how Bulgarian shops
price (per operation / price-list mentality). Optional informational duration.
Recorded by the performing technician or the Owner. Time tracking, timers, hourly
billing: future (V2+), the line model already accommodates them.

## 9. Photos & Attachments

Stage-tagged: приемане (recommended, protects both sides in disputes) · процес ·
завършен · друго. Limits: 10 MB/file, ~20/order, images + PDF, HEIC converted.
Retention: with the order. Local storage V1; path abstraction preserves cloud
migration (V2). Photos print as thumbnails on the intake protocol (optional toggle).

## 10. Customer Communication

ContactRecords (обаждане / имейл / съобщение / на място, direction, summary) — manual
in V1. Appear in the order timeline and on the customer profile. They never change
workflow status by themselves (recording a call ≠ approval; approval is its own
explicit action, which may reference the call). Edit window: author-only until end of
day, then frozen (OQ-1, pending PO).

## 11. Commercial Documents & Invoicing — workflow

```
Готова/terminal → [по желание] Фактура: Draft (редове от труд+части, ръчни редове,
корекция/отстъпка с причина) → преглед → ИЗДАВАНЕ (следващ пореден №, замразяване)
→ плащане(ия) → уредена
Корекция: Анулиране (причина) → нова чернова → ново издаване
```

- Worker may create drafts and record payments; **issuing and annulling are
  Owner-only by default** (per-company toggle to allow Workers — many 2-person shops
  need it). Pending PO confirmation (OQ-W1).
- Invoices optional per order; possible on Отказана/Неремонтируема (diagnostic fee).
- VAT handling per company mode (registered → lines with ДДС; non-registered →
  „нерегистрирано по ЗДДС" note) — **exact texts and fields from the accountant
  review** (Q2 decision).
- Cash payments: fiscal receipt comes from the shop's fiscal device; the product
  records the payment operationally. This boundary is stated in-product.

**Payments:** unified record (amount, method: в брой/карта/банков превод, date, note,
refund flag), many per order, optional invoice link. Deposit/partial/refund all
emerge from the one mechanism. Corrections by offsetting record.

## 12. Roles in the workflow (V1 permission matrix)

| Action | Owner | Worker |
|---|---|---|
| Customers/assets/orders: create, edit, statuses, tasks, parts, labor, photos, contacts | ✔ | ✔ |
| Анулирана transition, unarchive, bulk reassignment | ✔ | — |
| Invoice draft + payments | ✔ | ✔ |
| Invoice issue/annul | ✔ | toggle |
| Company settings, users, requisites, subscription/license | ✔ | — |
| Backup/restore, support package, GDPR anonymize | ✔ | — |
| Archive orders/customers | ✔ | ✔ (orders only) |

## 13. PDF Documents (V1 = exactly two)

1. **Приемо-предавателен протокол** — one template, two moments: intake (customer +
   asset + complaint + accessories + estimate range + terms + signatures) and delivery
   (work summary, warranty days, accessories returned, price, signatures).
2. **Фактура** — per accountant-approved template.
Estimate printout, warranty certificate, labels → V1.5.

## 14. Search — priorities

P1 (instant, normalized): phone (digits-only match) · order № · customer name
(Cyrillic/Latin tolerant). P2: IMEI / serial / VIN / рег. № (digits+letters
normalized). P3: invoice № · status · technician (filters, not free text). One search
box, grouped results (Клиенти / Поръчки / Активи), tenant = the single company.

## 15. Dashboard — "what requires attention today?"

Six operational widgets, each opening its filtered list/board: Активни поръчки ·
Чака части · Готови за получаване (with "over N days" highlight) · Просрочени
(promised date passed, non-terminal) · Днешни задачи · Обади се на клиента (open
call tasks). No charts, no vanity metrics.

## 16. Kanban

Columns = working + ready statuses (Тестване hidden if disabled); terminal orders
leave the board (reachable via search/lists). Card: order № · customer · asset ·
one-line complaint · technician initials · days-in-status · badges (просрочена,
приоритет, гаранционна). Filters: technician, priority, overdue. Colors communicate
urgency only (never the sole signal — badges carry text). Drag-and-drop: permission-
checked, matrix-validated server-side, optimistic UI with rollback + clear error
(„Иван премести поръчката преди теб"), approval/rejection prompt when leaving Чака
клиент, delivery prompt when dropping on Предадена. Non-drag path: status buttons on
card menu and order screen (tablet/mobile primary). Concurrency: last-write-wins with
conflict toast + board refresh on focus.

## 17. A Day — Owner (Мария, автосервиз, 6 души)

07:45 отваря таблото: 2 просрочени, 3 готови от >5 дни, 4 задачи „обади се". 08:00
преглежда Kanban, размества приоритети, назначава новия ремонт на Георги. 09:30 приема
клиент: намира го по телефона, нов актив (втора кола), поръчка + протокол — 2 мин.
11:00 одобрение по телефона за скъп ремонт → записва одобрението, мести в Чака части,
задача „поръчай накладки". 14:00 частите идват → received → Ремонт. 17:30 клиент
взима колата: плащане в брой, фактура (фирмен клиент), протокол, Предадена. 18:00
преглежда утрешните обещани дати; бекъпът е минал зелено (health индикатор).

## 18. A Day — Worker (Иво, GSM сервиз)

09:00 влиза с PIN на общия компютър. Таблото: 3 негови поръчки, 1 тест за днес. 09:15
Kanban → първата в Диагностика: оглед, диагноза (дисплей + батерия), оценка 180 €,
маркира „изисква одобрение" → Чака клиент, задача „обади се". 10:30 звъни, клиентът
одобрява → записва одобрението → Чака части. 11:00 друга поръчка: смяна на дисплей,
ред труд 60 €, снимки „процес", Тестване → Готова. 16:00 нов клиент на гишето: Иво
приема устройство (интейк + протокол — 3 мин, нов клиент). 17:45 отбелязва задачите,
PIN-out.

## 19. Failure Scenarios & Mitigations

| Scenario | Mitigation |
|----------|------------|
| Customer unreachable | Call task + escalating dashboard aging on Готова/Чака клиент; Owner archive-with-note as last resort |
| Lost/misplaced device | Order № on intake protocol; (labels V1.5); search by any identifier |
| Duplicate customer | Normalized-phone warning at creation; merge tool V1.5 |
| Duplicate order | Same asset + open order warning at creation |
| Wrong customer on order | Editable until first status change; afterwards Анулирана + recreate (history stays honest) |
| Duplicate/wrong invoice | Annul + reissue; gapless numbering preserved |
| Forgotten repair | Просрочени widget + days-in-status on every card |
| Technician absent | Owner bulk-reassign orders/tasks |
| Two users, same order | Optimistic concurrency, conflict toast, timeline arbitrates |
| Server PC off/crashed | Health check on start; daily verified backup; restore wizard; support package for remote diagnosis |

## 20. Open Questions (workflow)

- OQ-W1 Invoice issuing: Owner-only with per-company toggle for Workers — confirm?
- OQ-W2 „Готови от N дни" threshold default (proposal: 5 работни дни) — confirm?
- OQ-W3 Should intake photos be *required* (not just recommended) when the company
  enables a "strict intake" setting? (Proposal: setting exists, default off.)
- OQ-W4 Тестване: enabled by default for phone/electronics template, disabled for
  automotive — confirm?
- Plus OQ-1…OQ-5 from 01_DOMAIN_MODEL §7.

**Stop.** Awaiting review of 01 + 02. Next stage after approval: Part 6 —
Architecture Discovery (options, trade-offs, module boundaries, ADR candidates).
