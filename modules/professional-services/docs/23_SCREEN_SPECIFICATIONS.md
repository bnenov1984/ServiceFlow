# PS-23 — Screen Specifications

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Ten MVP screens. Common behaviours are stated once (§1) and not repeated;
each screen then defines the commissioned aspects that are specific to it.
Wireframes are deliberately absent — layout is implementation freedom within
[22]'s principles; *content and behaviour* below are normative. "Label" =
the org's configurable Assignment label.

## 1. Common behaviours (apply to every screen)

- **Loading:** skeleton rows/cards; no spinners-over-blank; slow (>3 s)
  shows a retry affordance. **Errors:** message-key-driven Bulgarian text +
  recovery action; form inputs preserved (NFR-PS-15).
- **Validation:** inline per field on blur + summary on submit; server
  errors map to fields via message keys.
- **Permissions:** actions absent (not disabled-mystery) for roles lacking
  them per [20] §3; server enforces regardless.
- **Audit:** every mutating action from any screen produces the activity/
  audit events defined in the model docs; screens add no exceptions.
- **Narrow screens:** per NFR-PS-20; anything not listed as adapted simply
  reflows read-only.
- **Accessibility:** [22] §4 baseline (keyboard, focus, labels-not-colour,
  contrast AA).

## 2. S-1 Dashboard (Табло)

- **Goal:** J-2 morning ritual — see all risk in <1 minute; P-4's whole UX.
- **Primary information:** bucket cards with counts, ordered: Просрочени ·
  За днес · Наближаващи · Без следваща стъпка · Блокирани · Без движение ·
  Чакащи документи · Чакащи клиента · Готови за предаване; money chip
  (просрочени плащания — money-visible roles); "моите" toggle filtering
  all buckets to current user.
- **Primary actions:** click bucket → S-2 pre-filtered; row peek within a
  bucket (top 5 by severity) with row actions (open, log call, complete
  action).
- **Empty state:** all-zero: "Няма рискове. Всичко е под контрол." + link
  to create Label; brand-new org: onboarding checklist (J-9): създай вид
  услуга → добави клиент → първа Label.
- **Mobile:** bucket cards stack; peeks collapse to counts.

## 3. S-2 Assignments list (Преписки — таблица / канбан / календар)

- **Goal:** find, sort, act (P-1 volume cockpit; Георги's "моята работа").
- **Table columns (default):** №, title, client, service type, stage (name
  + category icon), owner, next action (text + due + owner), official
  deadline (+risk badge), internal target, priority, last activity;
  money columns per visibility. Filters per FR-PS-080; text search; sort;
  archive toggle ([11] §4); totals row when money filtered (J-8).
- **Row actions:** open; change stage; complete/set next action; log
  communication; (manager+) change official deadline.
- **S-2a Kanban tab:** template picker (mandatory — one template at a
  time, [22] §3); columns = that template's stages; cards show №, title,
  client, risk badge, next-action due, owner avatar; drag = stage
  transition with the same guards ([12] §4) — guard prompts appear as
  dialog on drop; assignments of other templates listed under "извън тази
  дъска" link.
- **S-2b Calendar tab:** month/week; entries: official deadlines (risk-
  coloured + labelled), internal targets, appointments; click → S-4.
  No drag-to-move deadlines (deadline changes require the reasoned dialog).
- **Empty states:** no assignments → J-1 CTA; filter-empty → "изчисти
  филтрите" affordance.
- **Mobile:** table becomes cards (№, title, risk, next action); Kanban
  and calendar are desktop-only in MVP.

## 4. S-3 New assignment (Нова …)

- **Goal:** J-1 — register during a phone call in <60 s.
- **Fields (order):** client (typeahead + inline create C-1) → service
  type (loads defaults) → title → official deadline (+weekend/holiday
  badge) → owner (defaulted) → "още" collapsible: contact person,
  internal target, planned start, priority, description, price, typed
  details per service type ([09] §3.4).
- **Primary actions:** Запази (→ S-4 + next-action prompt N-9/J-1 ⚡);
  Запази и нова (batch intake).
- **Validation:** client, service type, title required; official deadline
  recommended-not-required (missing ⇒ "без краен срок" visibility, [13] §3);
  date sanity (deadline ≥ today warns, not blocks — backdated entry of
  already-late work is legitimate).
- **Empty/loading:** service types missing → inline link to S-7 (owner) or
  "помолете управителя" (worker).
- **Mobile:** fully supported — intake happens anywhere.
- **Audit:** creation event with initial snapshot.

## 5. S-4 Assignment details (the dossier screen)

- **Goal:** everything about one engagement; the "клиентът пита" answer
  screen (P4 in 10 seconds).
- **Layout blocks:** header (№, title, client→S-6, org-label, lifecycle
  state, stage + one-click transition, priority, owner, team); risk strip
  (official deadline + risk label, internal target, days left, deadline-
  history link); **next action panel** (description, owner, due, blocking
  reason; complete → N-4 dialog; replace); tabs/sections: Задачи и чеклист
  (progress, tick, add), Документи (requirements board missing/requested/
  received + dossier files by category, upload, preview), Комуникация и
  история (merged feed + quick-entry row [18] §2), Финанси (role-gated:
  agreed, entries, derived totals, payment due), Данни (typed details per
  service type), Връзки (follow-up links, CS-project link when [29] active).
- **Primary actions:** stage change; deliver (dialog: date, method,
  recipient); complete; cancel (manager+, reason); create follow-up
  ([11] §3); change deadlines (reasoned dialog); print/registry-extract F.
- **Validation:** per action dialogs; deliver requires delivery fields;
  cancel requires reason.
- **Empty states:** each panel teaches (no tasks → "добави чеклист или
  задача"; no requirements → "добави изискуеми документи").
- **Mobile:** read + quick actions (next action complete, log call, tick
  task, upload photo); heavy dialogs desktop-preferred but functional.
- **Audit:** the История tab *is* the audit surface for the record.

## 6. S-5 Clients (Клиенти)

- **Goal:** find/manage clients (C-*).
- **Info:** table: name, kind icon, phones, active assignment count,
  outstanding (money-visible), last communication.
- **Actions:** create (full form), open, deactivate (manager+).
- **Empty:** "Добавете първия клиент — или създайте го направо при нова
  Label."
- **Mobile:** cards; call links `tel:`.

## 7. S-6 Client details

- **Goal:** the relationship at a glance (C-3), fast answer when the bank
  calls about *their* assignments.
- **Info:** identity block (kind, contacts list, EIK, address, preference
  note); assignments table (state, stage, deadlines, risk — reuses S-2
  row component filtered by client); money summary (agreed/paid/
  outstanding across assignments); communications across assignments.
- **Actions:** edit; add contact person; new assignment pre-filled with
  this client; anonymize (owner, person-clients, guided [16] §4).
- **Audit:** client edits and anonymization are audit-logged; anonymization
  irreversible-warned.

## 8. S-7 Service types (Видове услуги)

- **Goal:** J-7 — Мария self-configures in minutes.
- **Info:** ordered list: name, active, defaults summary (workflow template,
  checklist, requirements count).
- **Actions:** create, rename, deactivate, reorder (drag with keyboard
  alternative); edit defaults: pick workflow template, checklist template,
  edit default-requirements list; (P: duration, default price/assignee).
- **Validation:** unique active names; deactivation blocked-with-
  explanation? No — allowed; existing assignments unaffected (copies),
  pickers hide it.
- **Empty:** offer the starter set (FR-PS-015) as one-click seed.
- **Permissions:** owner/manager only; **mobile:** desktop-only.

## 9. S-8 Workflow configuration (Работни процеси и чеклисти)

- **Goal:** shape templates safely ([12] §3, §5).
- **Info:** template list; editor: ordered stages (name, category picker
  with plain-language category explanations, drag-reorder), where-used
  (service types, active-assignment count on this template's copies).
- **Actions:** create (blank or copy of default/example), rename, edit
  stages, deactivate; delete only if never used; checklist-template editor
  (same screen, second tab: name + ordered items).
- **Validation:** 2–20 stages; ≥1 work category; missing delivery category
  warns ([12] §3); category is mandatory per stage.
- **Key reassurance UI:** "Промените важат само за нови Label" banner
  (copy semantics) — the single most confusion-prone fact, stated where
  the confusion would happen.
- **Permissions:** owner/manager; **mobile:** desktop-only.

## 10. S-9 Team (Екип) — two faces

- **S-9-view Натовареност (all roles):** per user: активни, просрочени,
  срок ≤3/≤7 дни, без следваща стъпка, блокирани, задачи за днес — counts
  linking to filtered S-2 (FR-PS-085). No estimates, no capacity bars
  (fake precision — [02] §2.3). Hidden entirely for single-user orgs.
- **S-9-admin Екип и роли (owner/manager):** user list (from Core
  identity) with module role assignment ([20] §2); no user creation here
  (Core owns users — link to platform user management).
- **Audit:** role changes audit-logged.
- **Mobile:** view face works (cards); admin desktop-only.

## 11. S-10 Notifications (Известия)

- **Goal:** the pull surface for [19] (badge in shell shows unacknowledged
  count).
- **Info:** grouped by severity then time; each: message, assignment link,
  age; digests expand ([19] §4).
- **Actions:** acknowledge (single/all-visible), snooze-until (date
  picker), open assignment; preference link → per-type opt-outs
  (FR-PS-092).
- **Empty:** "Няма нови известия." + link to preference settings.
- **Mobile:** fully supported — it is the phone-glance screen.
- **Audit:** acknowledge/snooze recorded per user (drives escalation
  honesty).
