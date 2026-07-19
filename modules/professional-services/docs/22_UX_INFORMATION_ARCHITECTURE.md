# PS-22 — UX Information Architecture

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Design constitution for [23_SCREEN_SPECIFICATIONS.md](23_SCREEN_SPECIFICATIONS.md).
Audience: P-1…P-4 — limited time, mixed digital literacy, Bulgarian-first.

## 1. Principles

1. **The dashboard answers before it is asked.** The ten commissioned
   questions (overdue? today? soon? blocked? no next action? unchanged?
   waiting docs? waiting client? ready to deliver? who's overloaded?) map
   1:1 to dashboard buckets/chips — nothing needs configuring to see them.
2. **Every list row acts.** Log a call, complete a next action, change a
   stage — from the row, without opening detail. The register survives only
   if writing costs seconds (P-3, J-1/J-4 budgets).
3. **Risk is words + icons, never colour alone** (NFR-PS-18); the same
   vocabulary ([04] §3) everywhere — bucket names = filter names = badges.
4. **Progressive disclosure:** daily screens carry zero configuration;
   settings (S-7/S-8/S-9-admin) are separate, owner/manager-only ([05] §5).
5. **No data loss:** forms keep state on error; destructive actions
   confirm; nothing auto-saves half-entities (NFR-PS-15).
6. **Org vocabulary everywhere:** the configurable Assignment label
   (ADR-PS-004) substitutes into titles, buttons, empty states via the
   i18n parameterisation ([31]).

## 2. Navigation map

```
Табло (S-1)
Преписки* (S-2: таблица | канбан S-2a | календар S-2b)  → S-4 детайл
   └─ Нова* (S-3)
Клиенти (S-5) → детайл (S-6)
Натовареност (S-9-view)
Известия (S-10)
Настройки  [owner/manager]
   ├─ Видове услуги (S-7)
   ├─ Работни процеси и чеклисти (S-8)
   ├─ Екип и роли (S-9-admin)
   └─ Организация (labels, thresholds, holidays, money visibility)
```

\* rendered with the org's label. The module contributes this nav to the
shared shell per the module contract (BOS-06 `navigation`); global search
(when platform-level) receives assignments/clients as module sources.

## 3. When which view (commissioned analysis)

| View | Best for | Poor for | Verdict |
|---|---|---|---|
| Dashboard buckets | daily control ritual (J-2), risk-first thinking | browsing everything | the **home screen**, always |
| Filterable table | high-volume firms (P-1: 120 valuations), sorting by any axis, money columns | spatial "where is everything" feel | **primary work view** — the default of S-2 |
| Kanban by stage | ≤ ~40 active of one workflow; stage-driven teams (supervision) | mixed workflows (columns explode), high volume | secondary tab, scoped to one template at a time |
| Calendar | appointment-heavy practices (inspections, hearings); week planning | status control | secondary tab (month/week) |
| Workload | Мария's assignment of new intake; spotting drowning colleagues | solo firms (hidden for single-user orgs) | own small screen |

The table default (not Kanban) is a deliberate break from card-app fashion,
justified by the valuation persona's volume; Kanban remains one click away.

## 4. Interaction & accessibility baseline

- Desktop-first layouts; narrow-screen (≥360 px): dashboard, my-work list,
  assignment detail (read + quick actions) fully usable; configuration
  screens may demand desktop (NFR-PS-20).
- Keyboard: full traversal of forms and row actions; `/` focuses search;
  visible focus rings; modals trap focus (NFR-PS-19).
- Dates typed as `дд.мм.гггг` or picked; all pickers show weekday + holiday
  badge ([13] §4).
- Empty states teach: each screen's empty state names the one action that
  makes it useful (J-9 onboarding rides on this, no separate wizard).
- Language: bg catalog only; tone: professional, short, no diminutives;
  errors say what to do next (`ps.*` keys, [31]).

## 5. Anti-complexity budget

A new screen, column, or setting must displace a named pain (P1–P12) or it
does not ship — the tripwire list in [02] §5 applies to UX first. Target:
a first-time P-3 user performs J-1 unaided in under a minute; if a usability
session fails that, the screen — not the user — is wrong.
