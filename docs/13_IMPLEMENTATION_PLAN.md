# 13 — Implementation Plan

Status: **v2.0 — restaged by Product Owner directive 11.07.2026** (supersedes the
v1.0 stage order; scope unchanged except where flagged) · Basis: everything frozen
in 07 · Planned for **one developer**; every stage ends runnable.

PO staging directive: freeze first → core operational flow → administration →
commercial documents. No AI features before the core flow works excellently.

## Етап 0 — Foundation & the ADR-002 gate *(in progress)*

Done: repo, module skeleton + import contracts, CI, health scaffold, spike
automation, local smoke run PASS, VM orchestrator, installer/bootstrap drafts.
**Open: the VM matrix run (PO executes, reports back) → gate decision.**
**No Alembic migration exists until the gate closes.** Code-signing certificate
procurement runs in parallel (PO task; longest lead time in the project).

## Етап 1 — Замразяване на архитектурата ✅ *(declared 11.07.2026)*

Architecture v1.0 = docs 03–07 + ADR-001…015 · Domain model v1.0 = doc 01 ·
Database schema v1.0 = doc 08 · API contracts v1.0 = doc 09 · UI navigation v1.0 =
doc 10 · Workflow v1.0 = doc 02. All PO-approved. From this point changes require
the 07 change process ("сериозна причина", written impact, PO approval, same-commit
doc/ADR amendment).

## Етап 2 — MVP: основният поток (Клиент → Поръчка → Актив → Задачи → Статуси → Бележки → Приключване)

Goal: a shop can run a repair end-to-end on the four screens. (~8–10 weeks solo)

- **Тънък identity срез** (not администрация): migration #1 (companies, users,
  sessions), login + sessions + CSRF, PIN switch, **one seeded owner user**. No user
  management UI, no invites — every action still has a truthful "who" (BR-5 is not
  deferrable; the timeline depends on it).
- Domain core: customers (normalization, duplicate warning), asset types + assets +
  identifiers, orders + numbering, statuses + full transition matrix (P0-1),
  timeline via domain events, global search (P0-7).
- Order operations: tasks (+call flag), notes, diagnosis (approval flow), part/labor
  lines as data (money math P0-3 — no documents yet), accessories, attachments,
  contact records.
- The four screens: intake flow (≤2 min target), Kanban + DnD + conflict handling,
  order detail, customer profile, dashboard.
- Приключване: terminal outcomes, delivery dialog (без документи — печатът идва в
  Етап 4), archive flag.
- Exit criteria: E2E journeys 1, 2, 4 (doc 12 §3) green; a non-developer completes
  intake→close unassisted.

## Етап 3 — Администрация (~4–5 weeks solo)

- Потребители и роли: invite/deactivate, Owner/Worker UI, permission matrix
  enforcement tests.
- Настройки: фирмени данни, статуси (rename/toggle), warranty defaults.
- **Архивиране и възстановяване**: backup artifact + nightly restore-verification +
  restore wizard + bare-metal path (05; P0-4).
- **Диагностика**: health page + tray, support package, opt-in телеметрия.
- Платформа: installer (walking skeleton → real), updater pipeline (04; P0-5),
  license client + grace + read-only (ADR-009), минимален vendor cloud (license
  API + update feed + admin console, A4 scope).

## Етап 4 — Commercial Documents (~4–5 weeks solo + accountant gate)

- **Приемо-предавателни протоколи** (intake + delivery print) — first item in the
  stage: it is the paper the customer leaves with, and the pilot is weak without it.
- **Оферти** — ⚠ scope flag: defined as *printable estimate from the diagnosis*
  (находка + препоръка + цена + срок + валидност). If PO means standalone quotes
  detached from orders, that is new scope needing a decision.
- Фактури: draft→issue→annul→reissue, gapless numbering (P0-2), VAT modes, PDF.
- Плащания: unified record, delivery-dialog settlement, „платена" state.
- **Gate: счетоводителят преглежда документите преди етапът да е готов (Q2).**

## Етап 5 — Hardening & пилот (unchanged from v1.0 Stage 7)

Reference-VM drills, security pass (11), performance budget (10 §9), one-page
документация за сервиза, **пилот: един реален сервиз, ≥2 седмици**, fix loop.
Launch gates unchanged: P0 green · drills green · accountant sign-off · пилотът
кара седмица без помощ · правен преглед на текстовете.

## Reconciliation notes (v1.0 → v2.0)

1. Identity split: v1.0 Stage 1 (пълна identity) → тънък срез в Етап 2 + пълна
   администрация в Етап 3. Причина: PO приоритет на потока; BR-5 запазен чрез
   seeded owner + PIN.
2. Протоколът се мести от intake потока (v1.0 Stage 4) в Етап 4 по PO директива —
   отбелязано, че пилот без протокол е неубедителен, затова е първи там.
3. Installer/updater/license се местят от „Stage 6" в Етап 3 (администрация),
   след потока. VM gate-ът остава преди всяка схема.
4. AI: нищо преди Етап 5+ (PO директива, съвпада с 00 roadmap).

## Out of scope — unchanged

Everything in 00 §Roadmap V1.5+ · SaaS beyond C1–C8 · configuration UIs seed data
covers. "Seemed easier while coding" is not a rationale (07).
