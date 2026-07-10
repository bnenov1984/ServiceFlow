# 10 — UI/UX Specification

Status: **Approved by Product Owner 10.07.2026** · Date: 10.07.2026 · Basis: 02, blueprint UX principles
Normative for V1: screens beyond this document require PO approval (ADR-004 risk
mitigation). All copy examples are the actual Bulgarian tone to ship.

## 1. Application frame

- **Top bar (always):** global search (`/` focuses it) · „+ Нова поръчка" (the one
  big primary button) · user chip (shows acting identity; click = PIN switch).
- **Left nav (5 items, never more in V1):** Табло · Поръчки (Канбан/Списък toggle) ·
  Клиенти · Фактури · Настройки (Owner sees all; Worker sees permitted subset).
- Health problems surface as one top banner (red/yellow) with a plain sentence and
  one action — never a notification center.
- Responsive: desktop = full layout; tablet = same; phone = nav collapses, Kanban
  becomes a status-grouped list with status-change buttons (02 §16 non-drag path).

## 2. The four core screens

### 2.1 Табло (Dashboard)
Six tap-through cards (02 §15), one row of today-focused numbers, nothing else.
Card anatomy: big number · label · worst-case hint („3 чакат > 5 дни"). Empty state:
„Няма нищо спешно. Спокоен ден 👌".

### 2.2 Поръчки — Канбан
Columns per enabled statuses (02 §16). Card: `№ 2026-00042` · customer name · asset
label · one-line complaint · technician initials · days-in-status chip · badges
(Просрочена / Приоритет / Гаранционна — text, not just color). Drag = status change
(server-validated); dropping on Предадена opens the **delivery dialog**; leaving
Чака клиент opens the **approval dialog**. Column header shows count. Filter bar:
Техник · Приоритет · Просрочени. List view: same data, sortable, for phone/preference.

### 2.3 Поръчка (Order detail) — one screen, no tabs
Header: № + status pill + big status-change buttons (allowed transitions only) +
print button (протокол). Two columns (stack on mobile):
- Left: Клиент (click-to-call `tel:` link) · Актив (identifiers visible) · Оплакване ·
  Диагноза (inline edit; approval block when required) · Суми (parts+labor computed,
  payments, balance — with „Добави плащане" and „Фактура" buttons).
- Right: Задачи (checklist add-inline) · Части (state chips needed→received) · Труд ·
  Аксесоари · Снимки (stage-tagged grid) · Комуникация (add call/visit note).
- Bottom, full width: Хронология (timeline, read-only, newest first).
Everything edits in place; no separate edit screens.

### 2.4 Клиент (Customer profile)
Header: name, phones (tel: links), duplicate warning if any. Sections: Активи (with
„Нова поръчка за този актив" shortcuts) · Активни поръчки · История · Бележки ·
Комуникация. „Анонимизирай (GDPR)" hides under Owner-only menu with a two-step
confirmation explaining consequences.

## 3. The intake flow (the 2-minute promise)

One screen, three collapsing steps, keyboard-first:
1. **Клиент** — phone-first search box; hit = select, miss = inline 3-field create
   (име, телефон, имейл?). Duplicate warning inline, non-blocking (BR from 02).
2. **Актив** — customer's existing assets as cards + „Нов актив": type picker (4
   icons), then that type's seeded fields; identifiers get format hints.
3. **Поръчка** — оплакване (textarea, required), аксесоари (checkbox row of common
   ones + free add: Зарядно, СИМ, Кутия, Ключ…), снимки (drag/camera), обещана дата
   (date + quick chips: Днес/Утре/3 дни/Седмица), приоритет, техник.
Submit → order created → **print dialog for протокол** opens immediately (the paper
the customer leaves with). Target ≤ 2 min existing customer / ≤ 3 min new.

## 4. Dialogs that carry business rules

- **Approval dialog** (leaving Чака клиент): Одобрено/Отказано · кой · как
  (телефон/на място/съобщение) · сума. Rejection requires one-line reason (OQ-2) and
  offers „Такса диагностика" invoice shortcut.
- **Delivery dialog** (→ Предадена): accessories checklist confirmation · balance
  due with „Добави плащане" · warranty days (default from settings) · „Фактура?"
  (по желание) · print протокол за предаване.
- **Annul invoice**: reason required; explains reissue path. Never worded as „изтрий".

## 5. Печат (print views)

Browser print, A4, clean CSS: протокол (intake and delivery variants — one template,
02 §13) and фактура. Print stylesheets are part of the component library, tested in
the E2E suite (a broken протокол is a launch blocker — it's the shop's legal-ish
paper trail).

## 6. Language & tone

Bulgarian business language everywhere (blueprint Part 6 examples are normative):
„Чака части", „Обади се на клиента", „Готова за получаване". Errors are sentences
with a next step: „Няма връзка със сървъра. Проверете дали компютърът на бюрото е
включен." Buttons are verbs: Запази · Приеми · Предай · Издай фактура. No jargon:
никога „статус трансакция", „workflow", „запис".

## 7. Accessibility & input (pragmatic set)

Keyboard: `/` search · `N` нова поръчка (from lists) · Enter-through on intake ·
Esc closes dialogs. Focus states visible; forms with labels (no placeholder-only);
status conveyed by text+color; drag-and-drop always has button equivalent; touch
targets ≥ 44 px. Full WCAG audit is not a V1 gate — these basics are.

## 8. Empty states & first-run

Every list's empty state teaches: „Все още няма поръчки. Създайте първата с бутона
горе." First run (after install wizard): checklist card on Табло — Фирмени данни ✓ ·
Първи клиент ✓ · Първа поръчка ✓ · Пробен печат ✓ · Резервно копие настроено ✓.
Disappears when done. This replaces any tour/tutorial system.

## 9. Performance perception budget

Search results < 300 ms perceived · Kanban drag feedback instant (optimistic, 02
§16) · dashboard < 1 s · intake submit-to-print < 2 s. On LAN hardware these are
comfortable; they are stated so regressions are visible.
