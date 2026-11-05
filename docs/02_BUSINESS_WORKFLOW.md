# 02 — Business Workflow

Status: **Approved by Product Owner 10.07.2026 — all open questions (OQ-W1…OQ-W4) accepted with proposed defaults** · Date: 10.07.2026
Input: Blueprint Part 4 + Discovery decisions (00) + Domain Model (01)
Business document: how the shop works and how the software supports it. No technology.

---

## 1. Status Model (approved simplified model)

*(Cleanup batch amendment, per Wave 2 Issue 5:)* Тестване was removed as a
separate status — verifying a repair is now simply part of Ремонт, never a
distinct stage a company can toggle. The table below reflects the current
**six working/waiting/ready statuses + four terminal outcomes** + archive
flag; the row it removed is struck out rather than deleted, so the change is
visible rather than silently rewriting history.

*(order-workflow-revamp WP-G, Q1, 05.11.2026:)* **Приета is display-renamed
НОВА** — the code (`received`) and its position in the model are unchanged,
only the Bulgarian label. НОВА has its own dedicated screen and a reduced
action set (§2 below) rather than the generic status menu every other
status gets — see §15's order-detail-page note and docs/15 §6.5.

*(Wave 4 audit correction, 25.09.2026, applied retroactively to this table —
not previously reflected here:)* **Предадена was renamed Приключена** — the
distinct post-Готова completion step reuses the pre-existing terminal-success
status rather than adding a new one.

Internal semantic kinds are fixed; Bulgarian display names are what users see.

| # | Status (BG) | Kind | Purpose — the question it answers |
|---|-------------|------|-----------------------------------|
| 1 | НОВА | working | Intake done; nobody has looked at it yet |
| 2 | Диагностика | working | A technician is evaluating it |
| 3 | Чака клиент | waiting | Estimate given; customer must decide |
| 4 | Чака части | waiting | Approved; blocked on parts |
| 5 | Ремонт | working | Actively being repaired (now includes verifying the repair — see amendment above) |
| ~~6~~ | ~~Тестване~~ | ~~removed~~ | ~~Verifying the repair~~ — folded into Ремонт |
| 6 | Готова | ready | Done; waiting for pickup |
| 7 | Приключена | terminal-success | Customer took it; engagement complete |
| 8 | Отказана | terminal-failure | Customer declined the estimate / shop declined the job |
| 9 | Неремонтируема | terminal-failure | Cannot / not worth repairing |
| 10 | Анулирана | terminal-failure | Created by mistake / duplicate |

**Архивирана is a flag, not a status** — applies to any terminal order; hides it from
operational views; reversible by Owner.

## 2. Transition Matrix

*(order-workflow-revamp WP-G, Q1–Q4, grilling 24.10.2026 — full rewrite of
this section; the prior matrix, kept only in git history now, let every
status skip-ahead to almost any other with a warning and allowed backward
moves through the same menu as forward ones.)*

Rows = from, columns = to. ✔ allowed (regular status menu) · W = allowed with
warning (skip) · ↩ = allowed **only** via the separate "Върни към…" action
(mandatory reason, never the regular menu) · — not allowed, not even with a
warning. All transitions require an authenticated user; backend always
validates (the UI is never the only gate).

**Анулирана is not a matrix cell at all** — it's reachable from any open
status via a separate Owner-only action (unconditional, mandatory reason),
same as before this rewrite; it's omitted from the table below for that
reason, not because it became unreachable.

| From \ To | Диагн. | Чака кл. | Чака части | Ремонт | Готова | Приключена | Отказана | Неремонт. |
|---|---|---|---|---|---|---|---|---|
| НОВА | ✔ | — | — | — | — | — | ✔ | — |
| Диагностика | — | ✔ | ✔ | ✔ | W | — | ✔ | ✔ |
| Чака клиент | ↩ | — | ✔ | ✔ | W | — | ✔ | — |
| Чака части | ↩ | ✔ | — | ✔ | W | — | ✔ | — |
| Ремонт | ↩ | ✔ | ✔ | — | ✔ | — | — | — |
| Готова | — | — | — | ↩ | — | ✔ | — | — |
| terminal | — | — | — | — | — | — | — | — |

Rules encoded above:
- **НОВА has no regular status menu at all** (Q2c) — just two dedicated
  actions: **ПРИЕМИ** (→ Диагностика, pre-fills whatever technician intake
  already picked — Q2b) and **ОТКАЖИ** (→ Отказана). Анулирана stays
  available as the usual Owner-only secondary action.
- **Диагностика requires a technician already on file to enter** (Q2a),
  server-side, every entry point — since НОВА only forwards to Диагностика,
  this single check also guarantees every later working status has one. A
  pre-WP-G order with no technician gets one at its next transition.
- **Неремонтируема is reachable only from Диагностика** (Q4) — not from any
  other status, reversing the prior model where several statuses allowed it.
- **Приключена only from Готова** (you can't hand over what isn't ready).
  Delivery prompts: accessories return check, warranty days, payment
  settlement, optional invoice, protocol print.
- **Backward movement (↩) is a separate action, "Върни към…", never the
  regular forward menu** (Q3) — always requires a reason (Q3b), always
  timeline-logged with the actor and the reason. Чака клиент/Чака части/
  Ремонт can all go back to Диагностика this way; Готова can go back to
  Ремонт. Available to any active user, not just the Owner.
- **Skips are still allowed with a warning** (small shops legitimately jump
  straight to Готова for trivial jobs) — unchanged by this rewrite, just
  narrower now that НОВА itself has no skip-ahead options at all.
- **Чака клиент exit to a forward status requires a recorded approval**
  (BR-7); exit to Отказана requires a recorded rejection. The backward move
  back to Диагностика is not "the customer's decision" and doesn't go
  through this gate — its own mandatory reason (above) covers it instead.
- **Анулирана** (mistake) is Owner-only and requires a reason, from any open
  status (see note above the table).
- Terminal statuses accept no further transitions; only payments settling
  balance, protocol printing and archiving remain possible. *(BR-2
  amendment, 11.07.2026:)* exception — **Owner-only „Отключване" ≤ 24 h**
  after the terminal transition, mandatory reason, returns the order to its
  pre-closure status, timeline event `OrderUnlocked`. Unavailable on
  archived orders (unarchive first, Owner-only anyway). The UI's „Повторно
  отваряне" button on terminal orders creates a **new linked follow-up
  order** (the rule); unlock lives under the Owner menu (the exception).

Timeline events per transition: StatusChanged + specific events (EstimateApproved,
OrderReady, OrderDelivered…) per 01 §5. Notifications: none in V1 (V1.5 hooks noted).
Permissions: any active user may perform allowed transitions except Анулирана
(Owner-only); see §12 role matrix.

## 3. Main Workflow (refined happy path)

```
Клиент идва → Намери/създай клиент (търсене по телефон, предупреждение за дубликат)
→ Регистрирай/избери актив (при съществуващ: последни посещения + последен пробег;
   отворена поръчка → блок с връзка към нея) → Създай поръчка №2026-00042:
     оплакване (задълж.) · аксесоари чеклист (всеки профил освен автомобилен —
     order-workflow-revamp WP-H, Q16/Q16b) · снимки при приемане (препор.)
     · обещана дата · приоритет · техник (по избор)
→ ПЕЧАТ: приемо-предавателен протокол (A4) — клиентът си тръгва с него
→ НОВА: ПРИЕМИ (изисква техник — ако не е избран при приемането, пита тук;
   WP-G, Q2a/Q2b) → Диагностика, или ОТКАЖИ → Отказана
→ Диагностика: находка, причина, препоръка, оценка (цена/срок), нужда от одобрение?
   ├─ одобрение нужно → Чака клиент → обаждане → запис на одобрение/отказ
   └─ не → продължава
→ Части нужни? → ред „част“ от ценоразписа, издадена от наличност или поръчана
   (WP-J, Q15/Q15b) → Чака части при блокаж
→ Ремонт (incl. verifying the repair — no separate Тестване stage) → Готова
→ Клиентът идва: аксесоари върнати ✓ · плащане(ия) · [фактура по желание]
   · гаранционен срок · ПЕЧАТ: протокол за предаване → Приключена
→ (по-късно) Архивирана
```

Target times (success metrics): intake incl. protocol ≤ 2 min for existing customer,
≤ 3 min for new; delivery incl. payment ≤ 1 min; invoice generation ≤ 1 min.

## 4. Exceptional Flows (from the blueprint, mapped)

| Scenario | Handling |
|----------|----------|
| Customer rejects estimate | Чака клиент → Отказана (reason recorded); diagnostic fee invoiceable + payable on the terminal order; delivery of unrepaired asset via protocol print from Отказана |
| Repair impossible | → Неремонтируема; same fee/protocol options |
| Customer never returns | Готова + N days → dashboard warning („Готови от над N работни дни"); remains Готова until delivered or Owner archives with note (no extra status) |
| Wrong diagnosis | Back to Диагностика; diagnosis edited in place, timeline shows the change |
| Additional damage found | Back to Диагностика or Чака клиент with updated estimate; new approval required if estimate grew |
| Additional parts needed | Back to Чака части; new part lines |
| Invoice correction | Issued invoice → Annul (reason) → new Draft → Issue (new number, references annulled one) |
| Warranty return | New order linked to original; badge „Гаранционна“; original stays terminal |

## 5. Tasks — retired

*(Retired 04.11.2026 — order-workflow-revamp WP-H, Q17/Q17b.)* The task
feature (order-bound + company-level, the dashboard's „Днешни задачи“/„Обади
се на клиента“ widgets, and the never-actually-built auto-call-task job) is
gone from the product entirely — it never justified itself against the
`Готова` dashboard aging warning (§15), which already covers the one case
("customer never came back for it") tasks were meant to catch. Old
task-created/task-completed timeline entries from before this date are left
in place, unexplained by anything else in this document; the underlying
table is kept (not dropped) for now, to be removed in a later, separate
change.

## 6. Diagnosis & Customer Approval

Diagnosis answers: what's wrong · why · repairable? · cost · duration. One record,
edited in place, every edit timeline-logged. Approval model V1 (simplest operational,
per discovery S3): the shop calls/talks; a user records the outcome — who, when,
channel (телефон / на място / съобщение), and what was approved (amount). No customer
portal, no tokens, no SMS in V1. The recorded approval is the shop's operational
evidence, not a legal signature (protocol carries signatures).

## 7. Parts — V1 flow

*(Amended 05.11.2026 — order-workflow-revamp WP-I, Q12a/Q13d, ADR-BOS-013.)*
Anyone may add part lines, but **only from the shop's own price list** (the
catalog — Owner-maintained in Settings, ADR-BOS-013) — no hand-typed name or
price, for any role. Lines are
addable only while the order is in Диагностика, Чака клиент, Чака части or
Ремонт — never at intake, never once Готова (reverses the earlier
"addable at intake" design). States: **издадена (issued, from the shop's own
supply) → поръчана (ordered, must come from a supplier) → монтирана
(installed)** *(amended 05.11.2026 — WP-J, Q15/Q15b: splits a third state
out of the prior 2-state "ordered → installed" model; adding a line offers
only "issued" or "ordered" as the starting state, via two separate buttons —
"installed" is reached only by a later change. Marking a line поръчана from
a working status offers a one-click suggestion to move the order to Чака
части; marking the last remaining поръчана line издадена offers a one-click
suggestion back to Ремонт — both nudges only (Q5/Q5c), never automatic — the
order's status still changes only through a human action.)* „Чака
части" is used when the order is blocked. Repair may proceed before all
parts arrive (partial work is real). No reservations, no stock levels, no
returns-to-inventory in V1 (no inventory exists; the catalog is a price
list, not stock; "issued" above is a line state, never a stock movement) —
unused part lines are removed with timeline trace.

Each part line also carries a plain on/off warranty flag — defaults on,
never affects price, and carries no term of its own (the term is the
company-wide warranty text already printed on the delivery protocol)
*(amended 05.11.2026 — WP-J, Q14/Q14b/Q14c, replaces the prior months-at-the-
API-boundary field entirely; a protocol frozen before this change keeps
printing its stored months forever, never retroactively reconstructed)*.

## 8. Labor

*(Amended 05.11.2026 — order-workflow-revamp WP-I, Q12d, ADR-BOS-013.)*
Lines are priced **from the same catalog** as parts — either fixed-price
(unit бр., description × qty × unit price, matching how Bulgarian shops
price per operation) or **hourly** (unit час, qty a decimal number of
hours × hourly rate) — the Owner decides per catalog item which. Optional
informational duration stays free entry (never a catalog field). Recorded
by the performing technician or the Owner. Full time tracking/timers
remain future (V2+); the hourly unit above is the pricing half of that,
already real.

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

*(Amended 05.11.2026 — order-workflow-revamp WP-I, Q13, resolves docs/01 OQ-5:)*
"корекция/отстъпка с причина" above is the `OrderAdjustment` entity — added on
the **order**, Owner-only, signed amount + mandatory reason; it flows into the
invoice draft as a `source="adjustment"` line the same way part/labor lines do,
never edited as a bare invoice-line price.

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
| Customers/assets/orders: create, edit, statuses, parts, labor (from the catalog), photos, contacts | ✔ | ✔ |
| Анулирана transition, unarchive, bulk reassignment | ✔ | — |
| Price catalog: create/edit/archive/import *(WP-I, Q12b)* | ✔ | — (reads it to add lines) |
| Order adjustment (price correction) *(WP-I, Q13)* | ✔ | — |
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

*(Amended 04.11.2026 — order-workflow-revamp WP-H, Q17b: down to four widgets,
the two task ones retired along with the rest of the tasks feature.)*
Four operational widgets, each opening its filtered list/board: Активни поръчки ·
Чака части · Готови за получаване (with "over N days" highlight) · Просрочени
(promised date passed, non-terminal). No charts, no vanity metrics.

## 16. Orders list

*(Amended 03.11.2026 — order-workflow-revamp WP-K, Q19/Q19b: Kanban retired.)*
One table of orders: № · Статус · Клиент · Актив · Техник · Дни в статуса ·
Обещана дата. Status chips („Всички отворени" + each open status) and
filters: technician, priority, overdue. Default order: overdue first, then
longest in status. On phones the same data as stacked cards. The list does
not change statuses; that happens only on the order page.

## 17. A Day — Owner (Мария, автосервиз, 6 души)

07:45 отваря таблото: 2 просрочени, 3 готови от >5 дни. 08:00
преглежда поръчките, размества приоритети, назначава новия ремонт на Георги. 09:30 приема
клиент: намира го по телефона, нов актив (втора кола), поръчка + протокол — 2 мин.
11:00 одобрение по телефона за скъп ремонт → записва одобрението, мести в Чака части.
14:00 частите идват → поръчаната част става издадена → Ремонт. 17:30 клиент
взима колата: плащане в брой, фактура (фирмен клиент), протокол, Приключена. 18:00
преглежда утрешните обещани дати; бекъпът е минал зелено (health индикатор).

## 18. A Day — Worker (Иво, GSM сервиз)

09:00 влиза с PIN на общия компютър. Таблото: 3 негови поръчки, 1 тест за днес. 09:15
отваря първата поръчка → Диагностика: оглед, диагноза (дисплей + батерия), оценка 180 €,
маркира „изисква одобрение" → Чака клиент. 10:30 звъни, клиентът
одобрява → записва одобрението → Чака части. 11:00 друга поръчка: смяна на дисплей,
ред труд 60 €, снимки „процес" → Готова. 16:00 нов клиент на гишето: Иво
приема устройство (интейк + протокол — 3 мин, нов клиент). 17:45 приключва деня,
PIN-out.

## 19. Failure Scenarios & Mitigations

| Scenario | Mitigation |
|----------|------------|
| Customer unreachable | Escalating dashboard aging on Готова/Чака клиент; Owner archive-with-note as last resort |
| Lost/misplaced device | Order № on intake protocol; (labels V1.5); search by any identifier |
| Duplicate customer | *(Amended 03.11.2026 — WP-B, Q7/Q8)* Individuals: normalized phone unique — blocked inline with „Избери съществуващия"; companies: ЕИК unique — blocked inline |
| Duplicate vehicle | *(Added 04.11.2026 — WP-C, Q11)* VIN and рег. № unique per company — blocked inline with „Избери този автомобил" |
| Duplicate order | *(Amended 04.11.2026 — WP-D, Q6)* Same asset + open order (any non-terminal status, incl. Готова) **blocked** at the asset step and on create; link to the open order |
| Mileage lower than before | *(Added 04.11.2026 — WP-D, Q9/Q10)* Blocked; Owner-only confirmation stores the real reading with a flag + comment |
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
- ~~OQ-W4 Тестване: enabled by default for phone/electronics template, disabled for
  automotive — confirm?~~ **Resolved (Wave 2 Issue 5):** removed entirely rather
  than made toggleable — verifying the repair is now just part of Ремонт for
  every company/template. See §1's cleanup-batch amendment.
- Plus OQ-1…OQ-5 from 01_DOMAIN_MODEL §7.

**Stop.** Awaiting review of 01 + 02. Next stage after approval: Part 6 —
Architecture Discovery (options, trade-offs, module boundaries, ADR candidates).
