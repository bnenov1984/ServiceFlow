# Order-workflow revamp — Phase 1 discovery & audit

Status: **Phase 1 (discovery only)** · Date: 14.10.2026 · Baseline: `main` @ `88c13f8`
(working tree clean except the untracked, not-yet-started
`.scratch/unified-order-lines/`). No application code, docs or ADRs were
modified. Tests were **not** run (read-only audit, no local Postgres); last
recorded state per docs/13: 750 backend tests collected, 506/506 vitest green
(20.09.2026), CI green on `main`.

Input: PO list of 31 items (Bulgarian, verbatim below) + one mock-up image
`Screen_Status-NEW.xlsx` (14.10.2026 15:24).

Legend — **Status**: `missing` · `partial` · `complete` · `unclear`.
**Fact** = verified in code/docs at the cited path. **Assumption** = my
reading, needs PO confirmation.

---

## 0. Governing constraints found during the audit

| # | Constraint | Source | Why it matters here |
|---|---|---|---|
| C-1 | docs/01 (domain), 02 (workflow), 08/09/10 (schema/API/UI) are **frozen**; any change needs written rationale → impact assessment → PO approval → same-commit doc amendment | docs/07 §"Change process after freeze" | ≥14 items below amend frozen rules (BR-9, Task entity, transition matrix, duplicate-phone rule, PartLine states…) |
| C-2 | P0-1: transition matrix is exhaustively tested; regressions block release | docs/12 §1, `service_orders/statuses.py`, `tests/test_statuses.py`, `frontend/src/generated/transition-matrix.json` | #22, #31 (and the mock-up's "НОВА") change the matrix |
| C-3 | ADR-BOS-011: profile varies **asset fields and terminology only**; workflow stays common for every profile | `docs/adr/ADR-BOS-011…` §Decision 8 | #7 is in scope; profile-specific *workflow* would not be |
| C-4 | PO decision 28.07.2026: all five profiles seed **identical** asset types | docs/business-os/18 §15.1(1) | #7 reverses this decision |
| C-5 | Product is **live** (Render + Neon). docs/business-os/18 §15.1(2) says additive-first migrations apply once real tenant data exists | docs/13 Repo-Wide Status; docs/business-os/18 §15.1 | Removals (#9, #25) and state changes (#27) must not drop live data in one step |
| C-6 | Module boundaries: `business_os.identity` cannot import `serviceflow.*` | `backend/.importlinter`, CLAUDE.md rule 5 | #15/#16 technician workload can't be added to identity's `GET /users` |
| C-7 | ADR-007: content-addressed storage keys | `attachments/service.py` `_content_key` | #11 "rename" cannot rename the stored object; it's a display/download name |
| C-8 | No literal UI strings, `message_key` only | ADR-015, CLAUDE.md rule 4 | every new field-level error in #5/#6/#17/#22 needs bg.ts keys |
| C-9 | Recent PO decisions that items here reverse: Wave 2 Issue 33 (part states → 2), 2026-09-25 (part warranty in months), Cleanup Issue 26 (mileage required for automotive), 2026-09-25 unified-order-lines (labor = hours × rate) | see per-item notes | Must be explicitly re-decided, not silently overwritten |

---

## 1. Master change inventory

Columns compressed per item: **Desc** (original BG + intended outcome) ·
**Status** · **Touches** · **Deps/decisions** · **Conflicts/risks/questions**
· **ADR? / Migration?**

### Orders list

**#1 — Само списък на поръчки без блокове и драгване**
- Outcome (assumption): a plain list view of orders with no Kanban columns/drag-and-drop.
- Status: **partial** — fact: `orders/OrdersPage.tsx:55` already has `view: "kanban" | "list"` toggle; `OrdersList.tsx` exists (default on mobile / `?view=list`). Default is Kanban.
- Touches: `orders/OrdersPage.tsx`, `OrdersList.tsx`, `KanbanBoard.tsx`, `FiltersBar.tsx`.
- Questions: (a) replace Kanban entirely, make list the default, or a per-company setting? (b) What are "блокове" — the Kanban columns, or the card tiles inside the list? Kanban is in docs/02 §16 (frozen) — removing it is a C-1 change; changing the default is not.
- ADR: no (unless Kanban removed → docs/02 §16 amendment). Migration: no.

### New order — customer

**#2 — „+ нова поръчка за физ. лице и за фирма – адрес на няколко реда"**
- Outcome: multi-line address input for both individuals and companies at intake.
- Status: **partial** — fact: company address is a single-line `<input maxLength=500>` (`customers/CustomerCompanyFields.tsx:175`). Individuals have **no** address field at all — only the optional one-line delivery address (`NewCustomerForm.tsx`). Storage is a JSONB string (`company_requisites.address`, `delivery_address.address`), so a newline-containing string needs no schema change.
- Questions: is "address" for individuals a new field (main address) or just the delivery address? Do multiple lines need to be structured (street / city / postcode) or free text with line breaks? Invoice PDF / protocol rendering of multi-line address must be checked (`commercial/pdf.py`, `protocol.py`).
- ADR: no. Migration: no if free text; yes if structured fields. Invoice buyer snapshot → touches ACCOUNTANT_REVIEW gate if structure changes.

**#3 — Ако адресът за доставка е различен от адреса на фирмата – чекбокс и показване на полета**
- Outcome: delivery address hidden by default (= company address); checkbox reveals separate delivery fields.
- Status: **partial** — fact: `Customer.delivery_address` exists (migration 0027) and is always shown as an optional input; no "same as company address" semantics.
- Deps: #2 (address shape), #14 (prefill source).
- Questions: when unchecked, is the company address *copied* into `delivery_address` or is delivery address left NULL and resolved at read time? Applies to individuals too (they have no "company address")?
- ADR: no. Migration: no (UI + resolution rule).

**#4 — Дублиран телефон за фирма да не е грешка**
- Outcome: a phone may belong to several companies and individuals.
- Status: **complete** (fact) — `customers/service.find_duplicates_by_phone` produces a non-blocking hint for every customer type; nothing rejects duplicates. Only nuance: company creation still shows the amber "duplicate phone" hint (`CustomerStep.tsx`) — question: should companies show no hint at all?
- Conflict: interacts with #5 — the dup rule must be defined *per customer type pair* (individual vs individual? individual vs company?).
- ADR/Migration: no.

**#5 — Дублиран телефон за физ. лице = грешка, проверка още на полето**
- Outcome: block creation of a second individual with the same phone; inline error on blur.
- Status: **missing** — fact: today it's a post-create hint (customer is already created when the warning appears, `CustomerStep.tsx` header comment).
- Conflicts: docs/01 Customer ("created with duplicate-phone warning") and docs/02 §19 ("Normalized-phone warning at creation; merge tool V1.5") — **frozen rule change (C-1)**. Existing live data may already contain duplicate individuals — what happens to them? GDPR-anonymized customers have `phone=""` (must be excluded). Archived customers: do they count?
- Questions: does an individual's phone also clash with a company's phone (per #4 assumption: no)? Can an Owner override (e.g. family members sharing one phone)?
- Needs: new pre-check endpoint (e.g. `GET /customers/phone-check?phone=`), server-side enforcement in `customers.service.create/update` (frontend-only check would violate the "backend authoritative" principle).
- ADR: docs/01/02 amendment. Migration: no unique index possible (rule is type-conditional and data may already violate it) — service-level check.

**#6 — Дублиран БУЛСТАТ – проверка веднага на полето, в червено**
- Outcome: inline red error when the entered ЕИК already exists.
- Status: **missing** — fact: ЕИК is validated for checksum (`is_valid_eik`) but never checked for uniqueness anywhere.
- Questions: hard error (block) or red warning? (Wording "грешка"/"в червено" suggests block — needs confirmation.) Same ЕИК for a company's branches? Scope: tenant-wide, excluding archived/anonymized?
- Needs: check endpoint + server enforcement; existing-data duplicate scan before any enforcement.
- ADR: no (new rule, but not contradicting a frozen one — docs/01 says nothing on ЕИК uniqueness). Migration: optional partial unique index on `company_requisites->>'eik'` — only after a data audit on prod.

### New order — asset

**#7 — Типът актив да е зададен от вендора според типа сервиз; автосервиз → автоматично автомобил, без избор на тип**
- Outcome: no asset-type picker; the vendor-assigned business profile decides the type.
- Status: **partial** — fact: `business_profile` exists and is vendor-assigned (migration 0015, `AssetType.business_profile`), already gates mileage (`service.create`, `OrderStep.tsx:99`). But all profiles seed identical 4 types and `AssetStep.tsx` always shows the picker.
- Conflicts: reverses PO decision 28.07.2026 (C-4). ADR-BOS-011 §4/§5 already anticipates per-profile seeding ("a branch in `seed_default_types`") → **in scope of the ADR**, but needs the decision recorded.
- Questions: only automotive, or all profiles get exactly one type (phone_repair → Телефон; electronics/appliance/generic → ?). What happens to existing automotive tenants' non-vehicle asset types/assets (non-destructive per ADR-BOS-011 §7 — hide, not delete)? Can a vendor grant more than one type?
- ADR: amend ADR-BOS-011 / docs/business-os/18 §15. Migration: **yes**, data migration for existing tenants' `asset_types` (live data → additive, C-5).

**#8 — Дублиран автомобил при различни собственици / смяна на собственик – историята остава към автомобила**
- Status: **complete for VIN-identified vehicles** (fact): Wave 3 Issue 20 — partial unique index on VIN per tenant, `AssetOwnership` span history, `transfer_owner` endpoint + intake reuse/transfer UI (`AssetStep.tsx`), service history keyed on `asset_id` (`service.list_orders_for_asset`). **Gap**: vehicle without VIN — only reg-№ soft hint, a second Asset can be created and history splits.
- Question: is VIN mandatory for vehicles, or should reg-№ also be an identity key?
- ADR/Migration: no, unless reg-№ uniqueness is wanted.

**#9 — Аксесоари към актив да се премахнат изцяло** (+ #29 second half)
- Status: **missing** (feature fully exists today).
- Touches: `AccessoryItem` model/table, `lines.py`, router endpoints, `intake/AccessoriesChecklist.tsx`, `order/AccessoriesListSection.tsx`, `CompletionDialog.tsx` (return check), `protocol.py` (intake + delivery sections), `completion_snapshot.accessories`, timeline event labels, tests (`AccessoriesChecklist.test.tsx`, `CompletionDialog.test.tsx`, `test_protocol.py`, `test_order_operations.py`).
- Conflicts: docs/01 AccessoryItem entity + **BR-9** (frozen), docs/02 §2/§3/§13 (delivery prompts + protocol content). Live data: existing accessory rows and frozen completion snapshots must remain readable/printable.
- Question: removed for every profile, or just automotive (phone shops typically log charger/SIM/case)? "към актив" — note accessories belong to the *order*, not the asset, today.
- ADR: docs/01/02 amendment (BR-9 retired). Migration: none for hide; drop table only in a later, separate step.

### Photos

**#10 — Иконки „фотоапарат" и „папка": снимай сега / избери от устройството**
- Status: **missing** — fact: single drop-zone `<input type=file accept="image/*" multiple>` (`OrderStep.tsx:213`, `PhotosGrid.tsx`); no `capture` attribute.
- Notes: `capture="environment"` behaves differently per OS/browser (desktop ignores it). Applies to both intake and order page (shared component recommended).
- ADR/Migration: no.

**#11 — Преименуване по шаблон `<№ поръчка>_<пореден №>`**
- Status: **missing** — fact: original filename is not stored; download name is `{attachment.id}.{ext}` (`attachments/router.py:109`); storage key is content hash (ADR-007, C-7).
- Questions: order number contains a dash (`2026-00049`) → `2026-00049_1.jpg`? Numbering: per order across all stages, gapless after soft-delete? Where does the name surface (download, lightbox, ZIP export)?
- Needs: per-order sequence (new `seq` column, or derived at read time from created order — derived numbers shift when a photo is deleted).
- ADR: no (ADR-007 untouched if it's a display name). Migration: **likely yes** (`attachments.seq`).

**#12 — Малък тъмбнейл при ъплоуд**
- Status: **partial** — fact: order page grid uses server thumbnails (`?thumb=true`); intake shows filename chips only (`OrderStep.tsx:222`) because files upload after order creation.
- Needs: client-side preview (`URL.createObjectURL`) in intake.
- ADR/Migration: no.

### New order — parts, courier, technician

**#13 — Махане на частите от създаването на поръчка; части едва в Диагностика, от dropdown без свободен текст**
- Status: **missing** — fact: intake has a part-lines draft (Issue 29, `OrderStep.tsx`, `IntakePage.tsx` best-effort POSTs); parts are free-text (`PartLine.name`).
- Deps: "dropdown without free text" requires a **parts catalog** → depends on #28. Status-gating ("only in Диагностика") depends on WP-G.
- Conflicts: reverses Issue 29. docs/02 §7 "Anyone may add part lines during diagnosis/repair" — gating to Диагностика needs clarification (also Ремонт? Чака части?).
- ADR: yes via #28. Migration: via #28.

**#14 — Куриер + съществуващ адрес → автоматично попълване**
- Status: **complete** (fact): Wave 5 Issue 12 — `OrderStep.tsx:103` prefills from `Customer.delivery_address`.
- Gap vs #3: if the "delivery = company address" checkbox semantics land, prefill must fall back to the company address. Verify-only item.

**#15 — В dropdown-а за техник да се вижда колко поръчки има всеки**
- Status: **missing** — fact: dropdown lists active users only (`OrderStep.tsx:345`).
- Constraint C-6: count must come from RepairFlow (`service_orders`), not identity's `GET /users` — e.g. new `GET /orders/technician-load` (count of open, non-archived orders grouped by `technician_id`).
- Questions: "active orders" = all OPEN statuses incl. waiting/ready, or only working ones?
- ADR/Migration: no.

**#16 — Да се показват техниците без активни поръчки**
- Status: **missing**. **Ambiguous** — (a) filter to free technicians only, or (b) highlight/sort free ones first? (a) would make assigning a busy technician impossible.
- Deps: #15 (same data). Also: should Owner/non-technician users appear? (No "technician" role exists — any active user is offered today.)

### Mileage & repeat visits (vehicles)

**#17 — Пробег по-малък от предишно влизане → грешка на полето, блокиране; пробегът НЕ е задължителен**
- Status: **missing** (comparison) / **conflicting** (optionality) — fact: no monotonic check exists; mileage is **required** for `automotive_repair` (Cleanup batch Issue 26, `service.create` → `errors.orders.mileage_required`, `tests/test_automotive_mileage.py`).
- Conflict: "няма да е задължително" reverses Issue 26 — needs explicit PO re-decision.
- Data: previous value = max/latest `service_orders.mileage` for the asset (+ legacy `field_values.mileage`, see `router.py:568`). Server must enforce, not just UI.
- ADR: no (docs/01 silent). Migration: no.

**#18 — Байпас при по-малък километраж: въвежда се последната стойност + коментар + услуга „възстановяване на километраж"**
- Status: **missing**.
- Deps: #17; the "услуга" is a labor line from the price list → #28.
- Questions: who may bypass (Owner only?); is the comment a timeline note or appended to the complaint; is the real (lower) reading stored anywhere (legal/odometer-fraud sensitivity — recording that the shop "restored" mileage should be reviewed)?
- **Risk**: odometer rollback is a regulated topic; the bypass must never let the system store a lower reading without trace. Suggest legal/PO sanity check.

**#19 — Не може да се създаде поръчка за автомобил с неприключена поръчка**
- Status: **missing** — no open-order check exists in backend or intake.
- Conflict: docs/02 §19 "Duplicate order: same asset + open order **warning** at creation" — PO now wants a **block** (C-1 amendment). Also blocks warranty returns? (`warranty_return` requires the original to be *completed*, so not affected — but a second complaint while a car is in Ремонт would be blocked.)
- Questions: vehicles only or all assets? Which statuses count as "неприключена" (all OPEN incl. Готова)?
- ADR: docs/02 amendment. Migration: no.

**#20 — В историята да се вижда, ако автомобилът вече е приеман**
- Status: **partial** — fact: `VehicleHistorySection` on the order page (vehicles only) + `GET /assets/{id}/service-history`. Mock-up shows an "ИСТОРИЯ" link in the asset card. Unverified: whether intake shows prior visits when an existing vehicle is picked.
- Question: where exactly — intake step, order page, timeline?

### Order screen per status (the big block)

**#21 — Статус ПРИЕТА: само преглед + редакция на описанието + снимки + асоцииране на техник; при асоцииране → ДИАГНОСТИКА; без части/труд/задачи вдясно**
- Status: **missing** — fact: `OrderPage.tsx` renders the same sections for every non-ready status; `ReadySummary` (Issue 8) is the existing precedent for a status-specific presentation.
- Conflicts: assignment auto-triggering a transition is new behavior (docs/02 philosophy: humans move orders; currently `assign_technician` emits only `technician_assigned`). Technician can already be assigned at intake (#15) — would that create the order directly in ДИАГНОСТИКА? **Contradiction with the mock-up** (see #24): the mock-up shows status „НОВА" (Приета struck out) with ПРИЕМИ / ОТКАЖИ buttons and no technician field.
- ADR: docs/02 amendment (auto-transition). Migration: no.

**#22 — Приета → Диагностика без техник → съобщение „не е назначен техник"**
- Status: **missing** — fact: `change_status` has no technician precondition.
- Must be server-side (Kanban/list status menu are other entry points). Does it apply to Kanban drag too (Kanban may disappear, #1)?
- ADR: docs/02 §2 rule addition. Migration: no. P0-1 tests extended.

**#23 — При смяна към Диагностика екранът да се сменя; горе статусът да се рефрешва (седи си ПРИЕТА)**
- Status: **unclear — reported bug**. Fact: `OrderHeader.runStatusChange` invalidates `queryKeys.order` and the pill reads `order.status_code`, so by code reading it *should* refresh. Not reproduced in this audit.
- Likely shares a root cause with #30. Needs reproduction (prod? specific browser? Kanban vs header?).

**#24 — Статус Диагностика – различен екран (рисуване на екран – Венци; приложена снимка)**
- Status: **missing / unclear**. The attached image is named `Screen_Status-NEW` and depicts **status „НОВА"**, not Диагностика.
- Mock-up content (fact): header `№ 2026-00049` + status „НОВА" (Приета struck through) + „Печат протокол (приемане)" + **ПРИЕМИ** / **ОТКАЖИ** buttons; left: АКТИВ card with „ИСТОРИЯ" link (Пробег, Марка, Модел, Рег.№, VIN, Година), ОПЛАКВАНЕ with „Промени", СНИМКИ with stage tabs + „Качи снимки"; right: КЛИЕНТ, ХРОНОЛОГИЯ with „Добави коментар" and a magnifier (details) per event. Absent: technician, parts, labor, tasks, accessories, promised date, invoice, money.
- Open: is there a separate Диагностика mock-up to come from Венци? Does „НОВА" mean a **new first status** before Приета (status-model change, P0-1, migration of seed `order_statuses`) or just a rename of Приета? What do ПРИЕМИ and ОТКАЖИ transition to (Отказана? Анулирана?)? Where is technician assignment (#21) on this screen?

**#25 — Да се махне ЗАДАЧИ**
- Status: **missing** (Tasks fully exist).
- Touches: `serviceflow/tasks` module, `TasksChecklist.tsx`, dashboard widgets „Днешни задачи" / „Обади се на клиента" (`dashboard/router.py`, `DashboardSummary.tsx`), `tests/test_tasks.py`, timeline labels, isolation tests (P0-9 covers tasks).
- Conflicts: docs/01 Task entity, docs/02 §5, §15 (two of six dashboard widgets), §4 („Готова + N days → auto-created call task"), §19 (call tasks as mitigation) — frozen (C-1).
- Question: remove the module entirely, or only from the order page (company-level chores, call reminders stay)? What replaces "обади се на клиента"?
- ADR: docs/01/02 amendment. Migration: none to hide; drop later.

### Parts & labor

**#26 — Части: чекбокс „гаранция" вместо поле за срок; чекнат → цената на частта = 0**
- Status: **conflicting** — fact: 2026-09-25 PO decision implemented part warranty **in months** (`order-completion` issue 05, `PartLinesSection.tsx`, `PartLine.warranty_days`, used on the warranty protocol).
- Semantics clash: today "warranty" = warranty the shop *gives* on the part; the new checkbox reads as "replaced *under* warranty → free of charge" — a different concept. If so, the completion protocol's per-part warranty terms (order-completion spec) lose their source.
- Money: zeroing price must keep BR-3 (derived totals); should the original price be retained (show "0 / гаранционна") for reporting and invoice lines (invoice line at 0 €)? Accountant gate (docs/12 §4) if invoice content changes.
- ADR: likely no, but docs/01 PartLine amendment. Migration: **yes** (new boolean or reuse), plus decision on existing `warranty_days` data.

**#27 — Статуси на части: издадена (от склада), поръчана (→ поръчката отива в ЧАКА ЧАСТИ), монтирана**
- Status: **conflicting** — fact: Wave 2 Issue 33 simplified to 2 states `ordered`/`installed` (migration 0022, `lines.PART_STATES`).
- New: auto status transition when a part is "поръчана" — breaks "humans move orders" (docs/02), and interacts with the matrix (e.g. part ordered while in Приета → `received → waiting_parts` is a WARN skip; while Готова → not allowed). When does the order leave ЧАКА ЧАСТИ — automatically when all parts are issued/installed?
- "Издадена от склада" implies a warehouse — docs/01 says **no inventory in V1** (InventoryItem = future entity). Is this just a label or real stock?
- ADR: docs/01/02 amendment; possibly ADR if inventory appears. Migration: **yes** (state values + backfill).

**#28 — Цените на труд и части – предефинирани от ценова листа; без полета за писане на цени**
- Status: **missing** — no catalog/price-list entity exists; prices are free-entry (`PartLine.unit_price`, `LaborLine.unit_price`).
- Conflicts: (a) docs/01 PartLine "name (free text)"; (b) the open `unified-order-lines` spec (PO 2026-09-25: labor = hours × hourly rate) — must be reconciled before either is built; (c) docs/01 §7 risk mitigation „just make it 50 €" relies on adjustment lines — without editable prices, discounts need another path; (d) invoices: manual invoice lines stay editable?
- Questions: who maintains the list (Owner in settings? vendor per profile?); import format; price change history (lines must snapshot price at add-time — BR-3); VAT-inclusive or net; per-part brand/variant explosion for automotive (thousands of SKUs) — a pure dropdown may not scale.
- **ADR needed** (new RepairFlow entity/aggregate, ownership per ADR-BOS-003). Migration: **yes** (new tables, RLS FORCE, `company_id`, UUIDv7, isolation tests P0-9).

**#29 — В Диагностика да останат снимките с възможност за още; да се махне аксесоари**
- Status: photos **complete** (PhotosGrid is on every non-terminal status); accessories part = duplicate of #9.

### Status menu

**#30 — От статус „Чака клиент" → dropdown → „Чака части": статусът реално не се сменя. Да се оправи!**
- Status: **reported bug, root cause unconfirmed**. Fact: from `waiting_customer` any forward transition opens `ApprovalDialog` (BR-7, `OrderHeader.requestTransition`); the backend rejects without `approval.approved=true` (`service.change_status`). Code path looks correct on reading; no unit/E2E test covers the approval path from the header (`OrderHeader.test.tsx`, `e2e/repairflow/*` — only rejection is covered).
- Hypotheses to test (not verified): dialog not visible/closing on open (cf. fixed race d02e051), user cancels the dialog expecting a direct change, or stale cache as in #23.
- ADR/Migration: no. Fix needs reproduction first (diagnosing-bugs loop) + a regression test.

**#31 — В dropdown-а само предстоящите статуси; „Неремонтируема" само в ДИАГНОСТИКА**
- Status: **missing / conflicting** — fact: `allowedTransitions()` offers every matrix ✔/W target incl. backward moves.
- Conflicts: docs/02 §2 "Backward movement is allowed among working statuses (wrong diagnosis, additional damage, failed test)" and §4 exceptional flows (back to Диагностика / Чака части) — **frozen**. Hiding only in the UI while the backend still allows it = UI/backend divergence; changing the matrix = P0-1 change. Ремонт → Неремонтируема (and from Приета/Чака клиент/Чака части) is ✔ today.
- Questions: how do "additional damage found" / "additional parts needed" flows work without backward moves? Is the restriction UI-only or a rule? Unlock (BR-2) unaffected?
- ADR: docs/02 §2 amendment + P0-1 test update. Migration: no.

---

## 2. Current-state & architecture gap analysis

**What already exists (reduces scope):** list view (#1), non-blocking phone dup for all (#4), vendor-assigned business profile with per-company asset types and the `business_profile` column ready for per-profile seeding (#7), VIN identity + ownership history (#8), server thumbnails (#12 partial), courier address prefill (#14), vehicle service history (#20 partial), status-specific presentation precedent `ReadySummary` (#21/#24), photos on every open status (#29).

**Gaps by layer**
- *Domain/workflow (frozen):* duplicate-phone block (#5), open-order block (#19), technician precondition and auto-transition (#21/#22), forward-only + Неремонтируема restriction (#31), auto Чака части on part ordered (#27), removal of AccessoryItem/BR-9 (#9) and Task (#25), PartLine name/price no longer free (#13/#28), possible new status „НОВА" (mock-up).
- *New entity:* price list / catalog for parts and labor (#28 → #13, #18, #26). No precedent in RepairFlow; nearest is PS workflow templates (copy-on-create).
- *Schema:* attachment sequence (#11), part state values (#27), part warranty flag (#26), per-profile asset-type data (#7), catalog tables (#28), optional ЕИК index (#6).
- *API:* phone/ЕИК pre-check endpoints (#5/#6), technician load (#15/#16), last-mileage lookup can reuse `service-history` (#17).
- *Frontend:* status-driven order page composition (#21/#24), intake rework (#2/#3/#10/#12/#13/#17/#19), status menu (#31), orders list default (#1).
- *Bugs:* #23/#30 — status change not reflected; no automated coverage of the approval path.

**Architecture conflicts to flag (not to resolve silently)**
1. ADR-BOS-011 §8 forbids profile-specific *workflow*. #7 is fine (asset types). If later items become "automotive-only" (e.g. #9 only for automotive, #19 vehicles only, #17/#18), they must stay field/terminology-level or be explicitly reviewed against §8.
2. C-6: technician workload must be a RepairFlow endpoint.
3. C-7: renaming is a display/download name, not a storage rename.
4. C-5: product is live → removals are hide-first, drop-later; part-state change needs a backfill migration with a test like `test_migration_0022_*`.
5. Reversals of four recent PO decisions (C-9) — each needs an explicit "supersedes" note in its .scratch spec and in docs.

---

## 3. Blocking questions & decisions (for PO)

**Workflow / status model**
- Q1 Mock-up: is „НОВА" a **new first status** (before Приета) or a rename of Приета? What do ПРИЕМИ / ОТКАЖИ do? Is there a separate Диагностика screen from Венци (#24 refers to Диагностика, the image is "Status-NEW")?
- Q2 #21 vs mock-up: where is technician assignment on the Приета/НОВА screen, and does assigning at intake (#15) create the order directly in Диагностика?
- Q3 #31: is "forward-only" a hard rule (matrix change) or only what the dropdown shows? How are "wrong diagnosis / additional damage / more parts" handled without moving back?
- Q4 #31: Неремонтируема only from Диагностика — confirm removal from Приета, Чака клиент, Чака части, Ремонт.
- Q5 #27: may the system move the order to Чака части automatically? From which statuses? Who/what moves it out?
- Q6 #19: block or warning? vehicles only or all assets? does Готова count as "неприключена"?

**Data rules**
- Q7 #5: hard block for individuals — confirm the frozen "warning" rule is replaced; does individual-vs-company sharing stay allowed; Owner override; what to do with existing duplicates?
- Q8 #6: ЕИК duplicate — block or red warning?
- Q9 #17: mileage optional again for automotive (reverses Issue 26)?
- Q10 #18: who may bypass; is the actual lower reading recorded; legal comfort with "restoring mileage" as a billable service?
- Q11 #8: should reg-№ also identify a vehicle when VIN is missing?

**Catalog / money**
- Q12 #28: who maintains the price list, at what granularity, with what import path? Does it supersede the unified-order-lines "hours × rate" decision?
- Q13 #28: with no editable prices, how are discounts/adjustments done (docs/01 OQ-5 adjustment line)? Do manual invoice lines remain free?
- Q14 #26: does "гаранция" mean *repair under warranty → free part* (new meaning) or the shop's warranty on the part (current meaning, months)? If the former, where do per-part warranty terms on the protocol come from?
- Q15 #27: is "издадена от склада" a label only, or the start of inventory?

**Scope of removals**
- Q16 #9: accessories removed for all profiles or only automotive? Keep printing historic accessories on old protocols?
- Q17 #25: tasks removed entirely (incl. dashboard „Днешни задачи"/„Обади се") or only from the order page?
- Q18 #7: which single type for each non-automotive profile; behavior for existing assets of other types.
- Q19 #1: Kanban removed, or list as default/setting?

**Smaller clarifications**
- Q20 #2: individuals get a main address field? Free text multi-line or structured?
- Q21 #11: exact name format (`2026-00049_1.jpg`?), numbering after deletion.
- Q22 #15/#16: what counts as "active"; filter vs highlight free technicians.
- Q23 #23/#30: environment and steps to reproduce (prod/staging, browser, which entry point).

---

## 4. Initial dependency map

```
WP-A bugs (#23,#30) ───────────────┐ (same OrderHeader code)
                                   ▼
Q1,Q2,Q3,Q4 ──► WP-G status-driven order screen (#21,#22,#24,#31, part of #13/#29)
                     ▲          ▲
WP-H removals ───────┘          │
 (#9,#25,#29b)                  │
                                │
WP-I catalog (#28) ──► #13 (dropdown) ──┘
        │          ──► #18 (mileage-restoration service)
        │          ──► WP-J parts (#26,#27) ──► Q5 auto Чака части touches WP-G matrix
        └─ supersedes/reshapes .scratch/unified-order-lines

WP-C profile/asset (#7,#8,#20) ──► WP-D vehicle intake guards (#17,#18,#19)
WP-B customer form (#2,#3,#4,#5,#6,#14) — independent (only #14↔#3)
WP-E photos (#10,#11,#12) — independent (shared component with WP-G screens)
WP-F technician picker (#15,#16) — independent; consumed by WP-G (#21 assignment)
WP-K orders list (#1) — independent
```

Hard edges: #28 → #13, #18, #26 · #17 → #18 · #9 ≈ #29 · #15 → #16 · #21 ↔ #22 ↔ #24 ↔ mock-up · #3 → #14 · #23 ≈ #30.
Doc edges: every C-1 item needs its docs/01/02 amendment in the same commit as the code.

---

## 5. Proposed work packages (grouping only — execution order not final)

| WP | Items | Independently verifiable by | Needs decision | ADR/doc change | Migration |
|---|---|---|---|---|---|
| A — Status-change bug | #30, #23 | Repro + regression unit/E2E test on approval path & header refresh | Q23 | — | — |
| B — Customer intake form | #2, #3, #4, #5, #6, #14 | Field-level errors on blur; backend rejects dupes; existing-data scan report | Q7, Q8, Q20 | docs/01, 02 §19 (#5) | maybe (#6 index) |
| C — Profile-driven asset type | #7, #8 gap, #20 | Automotive tenant sees no picker; history visible at intake | Q11, Q18 | ADR-BOS-011 / bos-18 §15 amendment | yes (data) |
| D — Vehicle intake guards | #17, #18, #19 | API rejects lower mileage / open order; bypass leaves trace | Q6, Q9, Q10 | docs/02 §19 (#19) | — |
| E — Photo capture & naming | #10, #11, #12 | Camera/folder buttons; previews; download name pattern | Q21 | — | yes (#11 seq) |
| F — Technician workload picker | #15, #16 | Dropdown shows counts; endpoint isolation-tested | Q22 | — | — |
| G — Status-driven order screen | #21, #22, #24, #31, #13 (placement), #29 | Per-status screens; matrix tests (P0-1) updated | Q1–Q4 + new mock-ups | docs/02 §1–2, 10, 15 | only if „НОВА" status |
| H — Retire accessories & tasks | #9, #25, #29b | UI/endpoints gone; historic protocols still render | Q16, Q17 | docs/01 (BR-9, Task), 02 §5/§15 | hide now, drop later |
| I — Price list / catalog | #28 (+ enables #13, #18) | Catalog CRUD + line add by catalog item; isolation tests | Q12, Q13 | **new ADR** + docs/01/08/09 | yes (new tables) |
| J — Part lifecycle & warranty | #26, #27 | State backfill migration test; auto-transition rule tests | Q5, Q14, Q15 | docs/01 PartLine, 02 §7 | yes |
| K — Orders list mode | #1 | List-only (or default) view | Q19 | docs/02 §16 if Kanban removed | — |

Existing `.scratch/unified-order-lines` should be **paused** until WP-I/J decisions are made.

---

## 6. Proposed review & planning sequence

1. **PO review of this audit** — answer Q1–Q23; confirm which recent decisions (C-9) are superseded.
2. **Mock-up round** — request the Диагностика screen (and confirm Status-NEW semantics) from Венци before WP-G is specced.
3. **Frozen-doc change proposals** — draft, for approval (not committed), the amendments to docs/01, 02, ADR-BOS-011 and a new catalog ADR, per the docs/07 change process.
4. **Per-WP specs** under `.scratch/<wp>/spec.md` + `issues/` (repo issue-tracker convention), each with acceptance criteria and test plan; mark `ready-for-agent` only after its questions are closed.
5. **Fix order then** — likely WP-A first (no decisions needed beyond repro, de-risks WP-G), then independent WPs (B, E, F, K) in parallel with decision-heavy ones (I → J, C → D, H → G).

---

## 7. PO decisions — workflow/status model (Q1–Q5, grilling 24.10.2026)

| Q | Decision |
|---|---|
| Q1 | „НОВА" is a **display rename of Приета** — code `received` unchanged, no new status, no status migration. ПРИЕМИ = pick technician → Диагностика; ОТКАЖИ → **Отказана**. |
| Q1b | Диагностика screen (#24): Claude builds a **prototype** from the decisions so far; Венци corrects it (final say). |
| Q2a | Technician **required** to enter Диагностика and every later working status — **server-side**, all entry points (header menu, list, Kanban). Legacy orders without a technician must get one at their next transition. |
| Q2b | Every order is created as НОВА, even if a technician was picked at intake; ПРИЕМИ dialog pre-fills that technician (one-click confirm). |
| Q2c | From НОВА only: Диагностика (ПРИЕМИ), Отказана (ОТКАЖИ), Анулирана (secondary „⋯" menu, Owner-only as today). All skips (W) out of НОВА removed. No regular status dropdown on the НОВА screen. |
| Q3 | Status menu shows **forward moves only**; Чака клиент / Чака части are pauses, always offered from working statuses. Backward = separate „Върни към…" action with **mandatory comment** (timeline). Matrix keeps those cells ✔. |
| Q3b | Backward = → Диагностика (from Чака клиент, Чака части, Ремонт) and Готова → Ремонт. Any active user. |
| Q4 | Неремонтируема **only from Диагностика**, server-side rule. Found during Ремонт → back to Диагностика (with comment), then Неремонтируема. |
| Q5 | Marking a part „поръчана" (from a working status where Чака части is allowed) → **one-click suggestion** „Да премина ли в Чака части?" — no automatic transition. |
| Q5b | Exit from Чака части stays **manual**; any exit suggestion is decided together with Q15 (part states, WP-J). |

Resulting matrix (✔ forward · W skip warning · ↩ backward, comment required · — not allowed):

| From \ To | Диагн. | Чака кл. | Чака части | Ремонт | Готова | Приключена | Отказана | Неремонт. | Анулирана |
|---|---|---|---|---|---|---|---|---|---|
| НОВА (Приета) | ✔ | — | — | — | — | — | ✔ | — | ✔ |
| Диагностика | — | ✔ | ✔ | ✔ | W | — | ✔ | ✔ | ✔ |
| Чака клиент | ↩ | — | ✔ | ✔ | W | — | ✔ | — | ✔ |
| Чака части | ↩ | ✔ | — | ✔ | W | — | ✔ | — | ✔ |
| Ремонт | ↩ | ✔ | ✔ | — | ✔ | — | — | — | ✔ |
| Готова | — | — | — | ↩ | — | ✔ | — | — | ✔ |

Cell changes vs current `statuses.py`: Приета → Чака кл./Чака части/Ремонт/Готова W→—, Приета → Неремонт. ✔→—, Чака кл./Чака части/Ремонт → Неремонт. ✔→—. Backward cells stay allowed but gain the comment requirement. Plus the technician precondition (Q2a).

Downstream notes: Kanban backward drag must open the comment dialog (if Kanban survives, Q19). All of the above amends frozen docs/02 §1–§4 and P0-1 — change proposal: `.scratch/order-workflow-revamp/proposal-docs02-status-model.md` (**awaiting PO approval, not applied**). Observed drift: docs/02 still says „Предадена" although the status was renamed „Приключена" on 25.09.2026 — fix in the same amendment.

---

## 8. PO decisions — catalog & money (Q12–Q15, grilling 24.10.2026)

| Q | Decision |
|---|---|
| Q12a | **Strict catalog.** Every order line is picked from the catalog — no free text, no manual price on order lines. |
| Q12b | Owner maintains it: manual CRUD in Settings + **Excel/CSV import**. |
| Q12d | Labor items are either **hourly** (unit = час, qty in hours, decimal) or **fixed-price** (unit = бр.). Supersedes/absorbs the 25.09 "hours × rate" decision. |
| Q12e | Missing item → **Owner only** adds it, also inline from the picker („Няма я? → Добави в каталога"). |
| Q12f | Flat list: type (част/труд) · name · code (optional) · unit (бр./час) · sale price · unit cost (optional, Owner-only). No categories/variants. Price **snapshotted** onto the line at add-time (BR-3). |
| Q13 | Discounts = **order-level adjustment line** (signed amount + mandatory reason, Owner-only) — implements docs/01 OQ-5 on the order; becomes an `adjustment` invoice line. |
| Q13b | Manual (non-order) invoice lines stay **free**. |
| Q13c | Existing hand-written lines stay as-is (history, protocols, invoices); catalog applies to new lines only; no data migration of lines. |
| Q13d | Lines can be added only in **Диагностика, Чака клиент, Чака части, Ремонт** (server-side). Parts removed from the intake form (reverses Issue 29). |
| Q14 | „Гаранция" = the shop's warranty on the part (current meaning). Per-part **checkbox** replaces the months field; term from company settings. |
| Q14b | Checkbox does **not** change the price. |
| Q14c | Checkbox **on by default**. Already-issued protocols keep printing their stored months. |
| Q15 | „Издадена" is a **line state only** — no inventory. States: издадена · поръчана · монтирана (reverses Issue 33's two states). |
| Q15b | On add: two buttons „От наличност" (→ издадена) / „Поръчай" (→ поръчана, suggests Чака части). Existing `ordered` rows stay поръчана. |
| Q5c | Arrived part is marked издадена; when no поръчана line remains → one-click suggestion „Да премина ли в Ремонт?". |

Facts established during the session (not decisions):
- Order line prices are **net** (invoice `net = Σ(qty×unit_price)`, docs/01 Invoice) → catalog prices are net.
- `LaborLine.qty`, `PartLine.qty` **and** commercial `InvoiceLine.qty` are `int` — hourly labor (1.5 h) needs `numeric` qty on labor *and invoice* lines → touches the issued-invoice format → **accountant gate** (docs/12 §4) must confirm.
- docs/01 PartLine still lists 4 states (needed→ordered→received→installed) although Issue 33 reduced them to 2 — pre-existing doc drift, fixed by the amendment.
- `.scratch/unified-order-lines` is superseded in its pricing part; the "one combined list" UI intent survives and is re-specced on top of the catalog (WP-I).

Proposals (awaiting PO approval, not applied):
- `.scratch/order-workflow-revamp/proposal-ADR-catalog.md` (new ADR-BOS-013)
- `.scratch/order-workflow-revamp/proposal-docs01-lines.md`
- docs/02 §7/§8: appended to `proposal-docs02-status-model.md`

Q1b prototype (24.10.2026): https://claude.ai/artifact/SFkWn26Z2cdzsjAyoc665q — 3 layouts of the Диагностика screen (A two columns like the НОВА mock-up · B technician worksheet · C tabs + rail), in-memory only. Verdict from Венци pending; record it here and in the WP-G spec.

---

## 9. PO decisions — data rules (Q6–Q11, grilling 24.10.2026)

| Q | Decision |
|---|---|
| Q6 | **Block** a new order for an asset with an open order — **all asset types**; open = every non-terminal status **incl. Готова**. Error links to the open order. Extra work on a Готова order → ↩ Ремонт + new lines. Warranty returns unaffected (original must be completed). |
| Q6b | Block shown at the **asset step** of intake („Има отворена поръчка №… (статус) → Отвори я"); server re-checks on create. |
| Q7 | **Block** a second *individual* with the same normalized phone — server-side, inline error on blur, „Избери съществуващия клиент". Individual-vs-company phone clash stays allowed (#4). GDPR-anonymized excluded. No Owner override. |
| Q8 | **Block** duplicate ЕИК — inline red error, „Избери тази фирма". |
| Q9 | Mileage **optional** again for automotive (reverses Issue 26). If entered, must be ≥ highest recorded mileage for that asset (server-side). |
| Q10 | Lower mileage: **Owner-only** confirmation; the **actually read** value is stored with a flag „по-малък от предишния — потвърдено" + mandatory timeline comment. „Възстановяване на километраж" is an ordinary catalog item, not built in. Legal review of flag/protocol wording recommended before release. |
| Q11 | **Reg-№ unique per tenant** (alongside VIN) — inline error + „Избери този автомобил". Plate changes = asset edit. |
| Q7b | Uniqueness rules apply on **create** and on **change of the keyed field** only; legacy duplicates stay editable otherwise. Picker lists all matches. Owner gets a „Възможни дубликати" list in Settings (manual archive; merge stays V1.5). Prod duplicate scan before enforcement. |
| #20 (not audit Q20) | Vehicle history at **intake** (last visits: date, №, mileage, complaint; last mileage shown as the floor) + „ИСТОРИЯ" link in the order's asset card. |

Facts established during the session:
- `normalize_identifier` (shared_kernel) uppercases alphanumerics but does **not** fold Cyrillic/Latin look-alikes — „СА1234ВХ" (Cyrillic) ≠ „CA1234BX" (Latin). Reg-№ uniqueness needs a homoglyph fold (А В Е К М Н О Р С Т У Х) — technical, no decision needed; existing VIN/reg data must be re-normalized in the same migration.
- Uniqueness for ЕИК / reg-№ is enforced in the service layer (type-conditional, live data may violate it); partial unique indexes only after the prod scan is clean.

Doc amendments needed (proposal: `proposal-docs01-02-data-rules.md`, awaiting PO approval): docs/01 Customer lifecycle; docs/02 §19 „Duplicate customer" / „Duplicate order" rows; docs/02 §3 intake line; Issue 26 reversal noted.

---

## 10. PO decisions — removals, asset types, orders list (Q16–Q19, grilling 24.10.2026)

| Q | Decision |
|---|---|
| Q16 / Q16b | Accessories removed **for automotive only**, implemented as a **per-asset-type flag** (`accessories: false` on Автомобил, true elsewhere). Historic accessories keep rendering/printing on old protocols and completion snapshots. Nothing deleted. |
| Q17 / Q17b | Tasks removed **entirely**: order page checklist, dashboard widgets „Днешни задачи" / „Обади се на клиента", auto call-task on Готова + N days, company-level tasks. Reminder covered by the **existing** „Готови от над 5 работни дни" highlight (`dashboard/router.py` `READY_WARN_BUSINESS_DAYS`). Old task events stay in the timeline. Hide first; drop table later, separately. |
| Q18 / Q18b / Q18c | **Exactly one asset type per profile, no picker at intake**: automotive → Автомобил · phone → **Телефон / таблет** (new field „вид": телефон/таблет; IMEI optional) · electronics → **Устройство** (new; вид, марка, модел, сериен №) · appliance → **Уред** (new; вид, марка, модел, сериен №) · generic → Друго. Existing tenants: new type seeded, old types hidden (not deleted), legacy assets keep their type. Reverses PO decision 28.07.2026 (C-4). |
| Q19 / Q19b | **Kanban removed**. Orders = table: № · Статус · Клиент · Актив · Техник · Дни в статуса · Обещана дата; status filter chips („Всички отворени" + each open status) + technician / priority / overdue filters; default sort overdue first, then days-in-status desc; cards on phone. **No status buttons in the list** — status changes only on the order page. |

Facts established during the session:
- Tasks are visible/completable **only** on the order page today (`TasksChecklist.tsx`); the dashboard shows counts linking to /orders. Hence Q17a (order page only) would have orphaned them → PO chose full removal.
- ADR-BOS-011 §Decision 8 lists **accessories** among the things common to every profile → Q16b still amends §8 (accessories move to an asset-type property), in addition to §4/§5 (per-profile types).

Doc amendments needed (proposal: `proposal-removals-types-list.md`, awaiting PO approval): docs/01 Task entity + AccessoryItem/BR-9; docs/02 §3, §5, §15, §16; ADR-BOS-011 §4, §5, §8; docs/business-os/18 §15.1(1).

---

## 11. PO decisions — smaller clarifications (Q20–Q22, Q4b, grilling 24.10.2026)

| Q | Decision |
|---|---|
| Q20 (#2) | Address = **free-text multi-line** for companies and individuals; individuals get an optional main „Адрес". No schema change; invoice/protocol PDFs must render line breaks. |
| Q20b (#3) | Delivery address hidden behind „Адресът за доставка е различен" checkbox; unchecked → delivery **resolves to the main address at read time** (not copied). Both customer types. Courier prefill (#14) falls back to the main address. |
| Q4b (#4) | **No duplicate-phone hint for companies** (and none for individual-vs-company clashes). |
| Q21 (#11) | Photo name `<№ поръчка>_<n>.<ext>` (e.g. `2026-00049_1.jpg`); `n` per order across all stages in upload order; **never reused or renumbered** after deletion; used for download, lightbox caption, ZIP export. New `attachments.seq`; storage key unchanged (ADR-007). |
| Q22 (#15/#16) | Technician picker shows count of orders in **Диагностика + Ремонт** („Иво Петров · 3 активни"); free users (0) sorted first and tagged „свободен" — highlight, not filter. All active users listed, Owner included. Count served by a RepairFlow endpoint (C-6). |
| Q23 (#23/#30) | PO has no repro details → Claude reproduces both locally (diagnosing-bugs) before WP-G rewrites the status menu. |

No frozen-doc amendment expected for Q20–Q22 beyond docs/01 Customer attribute wording (address for individuals) — drafted at spec time.

### Q23 diagnosis (24.10.2026) — #23 and #30 reproduced, root cause found, NOT fixed yet

- Loop: `frontend/e2e/repairflow/zz-debug-status-bugs.spec.ts` (throwaway, untracked) against local stack (docker dev DB + uvicorn + vite), tests `EXACT #23` / `EXACT #30` — red 2/2 runs.
- Symptom reproduced exactly: status changed **from the orders list** (status buttons; Kanban drop uses the same refresh) → open the order → pill still shows the old status (Приета / Чака клиент). `page.reload()` shows the correct status → the server transition succeeded.
- Root cause: global `staleTime: 30_000` (`frontend/src/main.tsx`) + list/Kanban status changes invalidate only `["orders"]` and `["dashboard"]` (`OrdersPage.refreshOrders`), never `["order", id]` / timeline → the order page renders the cached old order for up to 30 s with no refetch. The header path (`OrderHeader.refreshOrder`) invalidates the order keys, so changes made on the order page itself work (tests `#23 header`, `#30 header` green).
- Same class, observed during the repro: a freshly created order is **missing from the orders list** for up to 30 s (intake never invalidates `["orders"]`).
- Proposed fix (awaiting PO go-ahead): one shared "order changed" invalidation used by every status/intake mutation — invalidate `["orders"]`, `["order", id]` (prefix, incl. timeline), `["dashboard"]`. Regression test at the e2e seam (the bug is a cross-page cache interaction; a single-component unit test cannot show it).
- WP-G/Q19 removes list status buttons and Kanban, which removes this entry point, but the stale-list-after-intake case remains → fix independently of WP-G.
- **Fixed 24.10.2026 on branch `fix/stale-order-cache` (uncommitted):** shared `invalidateOrderViews` (`frontend/src/lib/orderQueries.ts`) used by OrderHeader, OrdersPage (list + Kanban) and IntakePage; regression `frontend/e2e/repairflow/order-status-cache.spec.ts` (3 tests red without the fix, green with it, 2 runs); related e2e (status, delivery, rejection, intake) green; typecheck + vitest 529/529 green.

## 12. Doc-proposal approvals

| Date | Proposal | Verdict |
|---|---|---|
| 26.10.2026 | `proposal-docs02-status-model.md` (docs/02 §1–§4, §7, §8) | **Approved**, §16 Kanban sentence dropped (Kanban removed, Q19). Applied to docs/02 together with the WP-G code + P0-1 tests. |
| 26.10.2026 | `proposal-ADR-catalog.md` (ADR-BOS-013) | **Approved** as drafted. Fractional qty also on invoices; no accountant sign-off — app is pre-production, no real issued invoices. |
| 26.10.2026 | `proposal-docs01-lines.md` (docs/01 PartLine, LaborLine, CatalogItem, OrderAdjustment, OQ-5) | **Approved** as drafted. |
| 26.10.2026 | `proposal-docs01-02-data-rules.md` (docs/01 Customer/Asset, docs/02 §3/§19) | **Approved**, minus the prod duplicate scan and the „Възможни дубликати" list (pre-production, no real data — supersedes that part of Q9). |
| 26.10.2026 | `proposal-removals-types-list.md` (docs/01 Task/AccessoryItem/BR-9, docs/02 §3/§5/§15/§16, ADR-BOS-011, bos-18 §15.1) | **Approved**, simplified: tasks tables dropped now, old asset types replaced outright (pre-production). |

WP-F (technician picker, #15/#16/Q22) implemented 26.10.2026 — PR #6.

WP-K (orders list → table, Kanban removed; #1/Q19/Q19b) implemented
03.11.2026 — Kanban board, OrderCard, the old status-grouped mobile list and
OrderStatusActions all retired; `OrdersList.tsx` is now the single table
(desktop) / stacked-card (phone) component, no status-change controls in
it. `@dnd-kit/core` dropped (no remaining consumer). docs/02 §16 amended
per `proposal-removals-types-list.md`'s already-approved text (only that
section — the rest of that proposal belongs to WP-C/H, not yet applied);
§17/§18 "Kanban" narrative mentions updated to match. E2E
`order-status-cache.spec.ts` re-pointed to the only direction that still
exists (status changed on the order page → list must not be stale) since
list-driven status changes no longer exist.

WP-B (customer intake rules; #2–#6/#14, Q4b/Q7/Q7b/Q8/Q20/Q20b) implemented
03.11.2026. Backend: migration 0032 (`customers.address`, individual's own
main address); `customers.service` blocks a second individual on the same
normalized phone and a second company on the same ЕИК, at create and at
update-of-the-keyed-field (GDPR-anonymized excluded, since anonymize()
always archives too); two read-only pre-check endpoints
(`GET /customers/phone-check`, `/eik-check`) for the inline on-blur UX; the
old non-blocking `duplicate_ids` hint mechanism on `POST`/`PATCH
/customers` is retired (superseded — see below); `service_orders`'s
courier-address fallback now falls one step further to the customer's own
main address when `delivery_address` is unset. Frontend: `NewCustomerForm`
gets an individual main-address field, a company address `<textarea>`
(multi-line, Q20), and on-blur phone/ЕИК duplicate pre-checks with a
resolve-to-existing action (`onExistingFound` — CustomerStep resolves
directly like a search hit; the standalone NewCustomerPage falls back to a
plain profile link); `CustomerDeliveryAddressSection` is now checkbox-gated
("Адресът за доставка е различен", Q20b) and its read-only view falls back
to showing the main address (not stored, read-time only) when unset; new
`CustomerAddressSection` for an individual's own address on the profile
page. docs/01 Customer Lifecycle + docs/02 §19 "Duplicate customer" row
amended per `proposal-docs01-02-data-rules.md`'s already-approved text
(only the customer-duplicate portion — the Asset/vehicle and mileage rows
in that same proposal belong to WP-C/D, not yet applied).

**Real fallout found and fixed, not a design gap**: ~13 existing backend
tests across 6 files (`test_invoice_annul.py`, `test_invoice_issue.py`,
`test_invoice_list.py`, `test_invoice_order_linking.py`, `test_invoices.py`,
`test_manual_invoice.py`) had local `_order()`/`_customer()` test helpers
that created every test customer with the same hard-coded phone, relying on
the old "duplicate phone never blocks" behavior — now correctly rejected.
Fixed by giving each helper a guaranteed-unique phone per call (an
`itertools.count()`-backed generator in each file, since several call these
helpers in loops with no caller-supplied uniqueness to thread through).
