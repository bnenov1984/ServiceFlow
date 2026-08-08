# 15 — Frontend Design Document

Status: **Approved by Product Owner 13.07.2026.** Checklist resolved: nav items
Фактури/Настройки = **сиви** („Очаквайте скоро"); всичко останало по подразбиране
(диалозите, intake partial-failure поведението, idle PIN 5 мин, аксесоар-чиповете
Зарядно/СИМ/Кутия/Ключ). · Date: 13.07.2026
Basis: 10 (normative screens/UX), 09 (API contracts), ADR-004 (stack), ADR-015
(i18n), pragmatism directive. Scope: **Етап 2 only** — login/PIN + the four screens
+ intake + protocol print. Registration, settings, user management, billing UI are
Етап 3 and deliberately absent.

---

## 1. Technology decisions (final, with rationale)

| Area | Choice | Why (and what was rejected) |
|---|---|---|
| Core | React 18 + TypeScript strict + Vite | ADR-004, already scaffolded |
| Styling | Tailwind CSS + design tokens (§3) | ADR-004; no component library — the UI is 4 screens with strong custom identity; a library (MUI/Chakra) would fight the BG-business look and add bundle weight |
| Server state | TanStack Query v5 | ADR-004; conventions in §5 |
| Local state | React state only | No Redux/Zustand — nothing in 4 screens needs global client state beyond auth context (pragmatism directive) |
| Forms | React Hook Form | In the approved stack list; used for intake + dialogs |
| Routing | react-router v6 | Standard; route table §4 |
| Drag & drop | @dnd-kit/core | Maintained, accessible (keyboard sensors), small; react-beautiful-dnd is unmaintained. DnD is an enhancement — buttons are the primary path (10 §2.2) |
| i18n | The existing typed `bg.ts` catalog + tiny `t(key, params)` | ADR-015 requires keys, not a library. react-i18next adds runtime+config for a single-language launch; we add it (or ICU tooling) when a 2nd language actually lands. The catalog stays the single source incl. backend `message_key` rendering |
| API types | `openapi-typescript` generated from FastAPI's openapi.json (CI script) | Types can never drift from 09's implementation; hand-rolled thin fetch client on top (§5.1) |
| Dates | Native `Intl` (bg-BG) + tiny helpers | No dayjs/date-fns until a real need; DD.MM.YYYY + 24h per 13_LOCALIZATION rules |

## 2. Application shell

Per 10 §1, unchanged: top bar (global search · „+ Нова поръчка" · user chip → PIN
dialog) · left nav exactly 5 items (Табло · Поръчки · Клиенти · Фактури · Настройки)
· one health/error banner slot · no notification center.

Етап-2 honesty: **Фактури** and **Настройки** render as disabled nav items with
tooltip „Очаквайте скоро" (they exist in nav per frozen 10 §1; hiding them would
change the approved navigation, graying them keeps the promise visible). PO may
veto to hide instead.

**Фактури landed** (central invoice workspace, `/invoices`): a real `NavLink`
now, for both Owner and Worker (invoice reads are not Owner-gated) — the
grayed-placeholder note above describes the Етап-2 starting state, not the
current one. **Настройки** stays grayed for a Worker (Owner-only), unchanged.

## 3. Design tokens (Tailwind theme)

Single source: `frontend/src/theme.ts` → consumed by `tailwind.config`.

- **Status kind colors** (semantic, from docs/02 kinds — never per-status-code):
  `working` синьо (#2563eb range) · `waiting` кехлибар (#d97706) · `ready` зелено
  (#16a34a) · `terminal_success` неутрално сиво-зелено · `terminal_failure`
  неутрално сиво-червено. Every colored element carries text too (10 §7: color is
  never the sole signal).
- **Alert colors**: overdue червено (#dc2626) · priority-high оранжев badge ·
  info/neutral slate.
- **Typography**: system-ui stack; scale 14/16/18/24/32; line-height 1.5; numeric
  tabular for №/суми.
- **Spacing/radii**: Tailwind defaults + `rounded-lg` cards, 44px min touch targets
  (10 §7).
- **Density**: one density only (counter use, not data-grid ERP).

## 4. Routes

| Path | Screen | Guard |
|---|---|---|
| `/login` | Login | public |
| `/` | Табло (Dashboard) | auth |
| `/orders` | Kanban (десктоп) / статус-групиран списък (мобилен) + `?view=list` | auth |
| `/orders/new` | Intake (3-стъпков single screen) | auth |
| `/orders/:id` | Order detail | auth |
| `/customers` | Клиенти (списък + търсене) | auth |
| `/customers/:id` | Customer profile | auth |
| `*` | 404 → връзка към Табло | auth |

Guard = `/auth/me` bootstrap: 401 → redirect `/login` (preserving `?next=`).
PIN dialog е modal, не route (не сменя контекста на екрана).

## 5. Data layer

### 5.1 API client
Thin `api.ts` wrapper over fetch: `credentials: "include"`, `X-CSRF-Token` from the
bootstrapped `/auth/me` payload on every mutation, JSON envelope parsing. Errors
arrive as `{code, message_key, params, field_errors?}` (09 §1) → rendered via
`t(message_key, params)`; unknown keys fall back to `errors.internal`. 423
(read-only mode, Етап 3) already handled generically: global banner + disabled
mutations. Generated types from openapi.json give each endpoint its request/response
shape.

### 5.2 TanStack Query conventions
- **Query keys registry** (`queryKeys.ts`): `["me"]`, `["dashboard"]`,
  `["orders", filters]`, `["order", id]`, `["order", id, "timeline"]`,
  `["customers", q]`, `["customer", id]`, `["customer", id, "assets"]`,
  `["users"]`, `["asset-types"]`, `["search", q]`. Никакви ad-hoc ключове.
- `staleTime` 30s default; `refetchOnWindowFocus: true` — това е механизмът зад
  „board refresh on focus" (02 §16).
- **Mutations**: всяка мутация декларира invalidation списък (напр. status change
  → `["order", id]`, `["orders"]`, `["order", id, "timeline"]`, `["dashboard"]`).
- **Optimistic updates само за Kanban drag** (02 §16): local move → on 409
  (row_version) rollback + toast „Иван премести поръчката преди теб" + refetch. No
  other optimistic writes in Етап 2 (pragmatism: dialогите така или иначе чакат
  отговор).
- Search input: 300ms debounce, `keepPreviousData`.

### 5.3 Auth/session
`AuthProvider` държи `me` (вкл. `csrf_token`, `is_owner`, language). PIN switch
мутация → invalidate everything (`queryClient.clear()` е приемливо — смяната на
актьор е рядка и трябва да е чиста). Idle timer (конфиг, default 5 мин без
взаимодействие) → PIN prompt overlay (ADR-008 идентичността винаги видима).

## 6. Screens — hierarchy, data, states

Формат: компоненти → данни → error/loading/empty. Всички текстове през `t()`.

### 6.1 Login (`/login`)
`LoginPage → LoginForm(email, password, device_label auto)`.
Data: `POST /auth/login`. States: submitting spinner в бутона; 401 → полево
съобщение `errors.auth.invalid_credentials`; 429 → `errors.auth.locked_out` с
обратен таймер (15 мин). Empty: n/a.

### 6.2 Табло (`/`)
`DashboardPage → WidgetGrid → StatWidget ×6` (Активни · Чака части · Готови (с
"над N дни" highlight) · Просрочени · Днешни задачи · Обади се).
Data: `GET /dashboard` (един call — **backend prerequisite §10**). Всеки widget →
link към филтриран `/orders` или tasks view. Loading: 6 skeleton карти. Error:
една ErrorState карта с Retry. Empty (всичко 0): „Няма нищо спешно. Спокоен ден 👌".

### 6.3 Поръчки (`/orders`)
```
OrdersPage
├─ FiltersBar (Техник · Приоритет · Просрочени · view toggle)
├─ KanbanBoard (desktop ≥md)
│   └─ StatusColumn ×7 (open kinds; header: име + брой)
│       └─ OrderCard (№ · клиент · актив · 1-ред оплакване · инициали техник
│            · days-in-status chip · badges: Просрочена/Приоритет/Гаранционна)
└─ OrdersList (mobile <md или ?view=list) → StatusGroup → OrderRow + StatusButtons
```
Data: `GET /orders?state=open` + `GET /users` (инициали/филтър — **prerequisite**).
DnD: dnd-kit; drop → `POST /orders/{id}/status`; преходите се валидират клиентски
от **същата матрица, генерирана от backend теста** (`transition-matrix.json`
артефакт — виж §9) само за UX (забранени колони се затъмняват при drag); сървърът
остава истината. Drop на който и да е terminal статус не съществува на борда —
terminal преходите стават само през диалозите (§6.6). WARN преходи: toast
„Прескочихте стъпки" след успех.
Loading: колони със skeleton карти. Error: ErrorState + Retry. Empty: „Все още
няма поръчки. Създайте първата с бутона горе."

### 6.4 Intake (`/orders/new`) — целта ≤ 2 мин
```
IntakePage (единичен екран, 3 collapse секции, Enter-through)
├─ Стъпка 1 КЛИЕНТ: PhoneFirstSearch (debounce; резултати → избор) | InlineCreate
│    (име, телефон, имейл?) + DuplicateHint (неблокиращ, от duplicate_ids)
├─ Стъпка 2 АКТИВ: AssetPicker (карти на активите на клиента) | NewAssetForm
│    (type picker 4 икони → типизирани полета от GET /asset-types; identifier
│    format hints; duplicate_asset_ids hint)
└─ Стъпка 3 ПОРЪЧКА: оплакване (required) · AccessoriesChecklist (готови чипове:
     Зарядно/СИМ/Кутия/Ключ + свободно добавяне) · снимки (по избор, multipart)
     · promised chips (Днес/Утре/3 дни/Седмица/дата) · приоритет · техник
```
Submit последователност: (create customer ако нов) → (create asset ако нов) →
`POST /orders` → `POST accessories` bulk → (upload снимки) → **отваря
`/orders/{id}/protocol.pdf` в нов таб** (печатът е server PDF — решението от
Етап-2 backend-а; browser print CSS не се дублира) → redirect към `/orders/:id`.
Частичен провал (напр. снимка): поръчката е създадена, toast с какво не успя —
никога не губим интейка заради периферия. Error: полеви грешки от field_errors.

### 6.5 Order detail (`/orders/:id`) — един екран, без табове (10 §2.3)
```
OrderPage
├─ OrderHeader (№ · StatusPill · StatusActionButtons (само позволените от
│    матрицата; terminal през диалози §6.6) · Печат протокол · Owner меню:
│    Отключи (unlock) / Ново гаранционно / Архивирай)
├─ лява колона: CustomerCard (tel: link) · AssetCard (идентификатори) ·
│    ComplaintBlock (inline edit) · DiagnosisCard (inline form; approval блок
│    когато approval_required) · MoneyCard (parts+labor изчислени; редове
│    добавяне inline; „Фактура" бутон disabled с „Етап 4")
├─ дясна колона: TasksChecklist (+call flag) · PartLines (state chips
│    needed→ordered→received→installed) · LaborLines · AccessoriesList
│    (returned checkbox) · PhotosGrid (stage tabs; upload; lightbox) ·
│    ContactsList (+ добавяне: тип/посока/резюме; editable до края на деня)
└─ TimelineSection (пълна ширина, read-only, най-новите горе, actor + време)
```
Data: `["order", id]` + timeline + attachments + contacts (паралелни заявки; един
skeleton layout). Terminal orders: всичко read-only + banner с изхода и причината.
Error 404: „Няма такава поръчка" + link. Всички мутации → invalidation per §5.2.

### 6.6 Диалози, носещи бизнес правила (10 §4)
- **ApprovalDialog** (излизане от Чака клиент напред): Одобрено/Отказано · канал
  (телефон/на място/съобщение) · сума. Отказ → изисква причина + предлага
  „Такса диагностика" (disabled, „Етап 4").
- **DeliveryDialog** (Готова → Предадена): чеклист аксесоари върнати · warranty
  days (default от settings; поле) · бележка че плащане/фактура идват в Етап 4.
- **ReasonDialog** (Отказана/Неремонтируема/Анулирана · unlock): една причина,
  задължителна където правилата казват; Анулирана видима само за Owner.
- **PinSwitchDialog**: списък потребители (`GET /users`) → PIN pad (големи
  бутони) → swap; грешен PIN → изтръскване + `errors.auth.invalid_pin`.

### 6.7 Клиенти (`/customers`, `/customers/:id`)
Списък: SearchInput (име/телефон, същата нормализация се случва сървърно) +
CustomerRow (име, телефони tel:, брой активни поръчки — от list响 отговора).
Profile (10 §2.4): CustomerHeader (dup warning) · AssetsSection (+ „Нова поръчка
за този актив" → intake с preselect) · ActiveOrders · History (terminal) · Notes/
Contacts (общият ContactsList компонент). Owner меню: Анонимизирай (GDPR) —
двустъпково потвърждение с изброени последствия. Empty списък: teaching empty
state. Error/loading по общия шаблон.

### 6.8 Global search (header, `/` фокусира)
Dropdown с групи Клиенти/Поръчки/Активи (`GET /search?q=` — **prerequisite**),
клавиатурна навигация (↑↓ Enter), highlight на съвпадението. Loading: 3 skeleton
реда; Empty: „Нищо не е намерено за „…““.

## 7. Общи компоненти (shared/)

StatusPill · Badge (overdue/priority/warranty) · Money (EUR, bg-BG формат) ·
DateText (DD.MM.YYYY; relative за timeline: „преди 2 ч") · EmptyState(icon, text,
action?) · ErrorState(retry) · Skeleton варианти · ConfirmDialog · Dialog (ફокус
trap, Esc) · Toast система (успех/грешка/conflict) · PinPad · Avatar (инициали).

## 8. Responsive + достъпност

Breakpoints: Tailwind default; критичното: `<md` Kanban → статус-групиран списък
със StatusButtons (никакъв drag на телефон). Nav: `<md` bottom bar с 4-те активни
секции. Touch ≥44px. Клавиатура: `/` търсене · `N` нова поръчка (в списъци) ·
Esc затваря диалози · Enter-through в intake · dnd-kit keyboard sensor за борда.
Фокус видим навсякъде; формите с истински label-и; статус = текст+цвят.

## 9. Testing (per 12, frontend слоят)

- **transition-matrix.json**: генерира се от backend-а (малък script, тестван
  срещу `statuses.py`) и се консумира от клиента → клиентската матрица никога не
  се разминава с истината; E2E проверява, че забранен drop не праща заявка.
- Component tests (Vitest + Testing Library): диалозите от §6.6 (правилата!),
  StatusActionButtons срещу матрицата, intake стъпковата логика, PIN pad.
- E2E (Playwright): journeys 1, 2, 4 от 12 §3 + protocol print snapshot
  (PDF байтове съществуват и почват с %PDF; текстовата проверка вече живее в
  backend тестовете).
- Бюджет: компонентните в CI (<2 мин); E2E nightly + pre-release (12 §4).

## 10. Backend prerequisites (малки, спец'нати в 09, липсват в кода)

1. `GET /users` — id, name, is_owner, is_active (за PIN dialog, техник picker,
   инициали). Тривиален, identity module.
2. `GET /dashboard` — шестте броя + preview данни, един call (02 §15).
3. `GET /search?q=` — групирани резултати (P0-7; нормализацията вече е готова и
   тествана — остава заявката + endpoint).
4. Bonus (за §9): `transition-matrix.json` export script.

Имплементират се първи, преди UI кода, като част от одобрения Етап-2 обхват (те
са в замразения 09 — не е ново scope).

## 11. Non-goals (Етап 3+ — да не се появяват „между другото")

Регистрация/onboarding · настройки UI · управление на потребители · фактури/
плащания UI · известия · offline · тъмна тема · втори език (каталогът е готов за
него, UI-ят не го експонира).

## 12. Approval checklist за PO

- [ ] Диалозите в §6.6 покриват правилно бизнес правилата?
- [ ] Intake последователността (частичен провал не губи поръчката) — ок?
- [ ] Сиви (disabled) Фактури/Настройки в nav vs скрити — предпочитание?
- [ ] Idle PIN prompt default 5 мин — ок?
- [ ] Готови аксесоар-чипове: Зарядно/СИМ/Кутия/Ключ — списъкът верен ли е?

**Stop: чака одобрение. След „одобрявам" — §10 предпоставките, после екраните в
ред: shell+login → intake → order detail → kanban → dashboard/customers/search.**
