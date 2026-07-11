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

## Етап 2 — Core MVP (Клиент → Поръчка → Актив → Задачи → Статуси → Бележки → Приключване)

Goal: a shop can run a repair end-to-end on the four screens. (~8–10 weeks solo)
Refined by PO 11.07.2026.

- **login/PIN + seeded Owner** (тънък identity срез, не администрация): migration
  #1 (companies, users, sessions), login + sessions + CSRF, PIN switch. No user
  management UI — but every action has a truthful "who" (BR-5).
- Клиенти (normalization, duplicate warning) · Активи (types, identifiers) ·
  Сервизни поръчки (numbering) · Статуси + full transition matrix (P0-1) · Задачи
  (+call flag) · Бележки · diagnosis (approval flow) · part/labor lines as data
  (money math P0-3 — no documents yet) · accessories · attachments · contact
  records · **timeline с actor attribution** (domain events) · global search (P0-7).
- **Приключване**: terminal outcomes, delivery dialog (payments/invoices идват в
  Етап 4), archive flag.
  ⚠ **„Повторно отваряне" — OPEN, colides with frozen BR-2** (no reopen; follow-up
  = нова свързана поръчка). Needs PO decision via the 07 change process before
  Етап 2 codes it — see the two options in the plan-v2.1 note below.
- **Минимален приемо-предавателен протокол** (PO change, accepted): one A4 print
  at intake — shop header, order №, date, customer, asset, complaint, accessories,
  signature lines. The *extended* protocol (delivery variant, estimate, warranty,
  terms text) stays in Етап 4.
- The four screens: intake flow (≤2 min target incl. protocol print), Kanban + DnD
  + conflict handling, order detail, customer profile, dashboard.
- Exit criteria: E2E journeys 1, 2, 4 (doc 12 §3) green incl. protocol print
  snapshot; a non-developer completes intake→close unassisted.

## Етап 3 — Operations & Administration (~4–5 weeks solo)

- Users/roles: invite/deactivate, Owner/Worker UI, permission matrix enforcement
  tests.
- Settings: фирмени данни, статуси (rename/toggle), warranty defaults.
- **Backup/restore**: artifact + nightly restore-verification + restore wizard +
  bare-metal path (05; P0-4).
- **Diagnostics**: health page + tray, support package, opt-in телеметрия.
- Installer (walking skeleton → real) · updater pipeline (04; P0-5) · licensing
  (ADR-009: grace + read-only) + минимален vendor cloud (A4 scope) ·
  **code signing** (cert procured in parallel from Етап 0; wired into the build
  here).

## Етап 4 — Commercial Documents (~4–5 weeks solo + accountant gate)

- **Диагностична оферта към поръчка** (PO-confirmed definition): printable estimate
  from the order's diagnosis — находка, препоръка, цена, срок, валидност. Not
  standalone quotes.
- **Разширени протоколи**: delivery variant, estimate/warranty/terms text blocks,
  accessories-returned confirmation (extends the Етап-2 minimal protocol).
- Фактури: draft→issue→annul→reissue, gapless numbering (P0-2), VAT modes, PDF.
- Плащания: unified record, delivery-dialog settlement, „платена" state.
- **Счетоводен gate: review преди етапът да е готов (Q2).**

## Етап 5 — Hardening & Pilot

Security hardening (11 checklist) · performance budget (10 §9) · **recovery
drills** (04 §6 + 05 §7 on the reference matrix) · **реален сервиз ≥2 седмици** ·
обратна връзка + fix loop · release readiness: P0 green, drills green, accountant
sign-off, пилотът кара седмица без помощ, правен преглед.

## Reconciliation notes (v2.1, PO refinement 11.07.2026)

1. Минималният протокол се връща в Етап 2 (PO change) — разширените протоколи
   остават в Етап 4.
2. „Оферти" дефинирани като диагностична оферта към поръчка (PO-confirmed).
3. ⚠ **OPEN: „повторно отваряне"** противоречи на замразения BR-2 (терминална
   поръчка не се отваря; гаранционно връщане/продължение = нова свързана поръчка).
   Options: (a) keep BR-2 — reopen = create linked follow-up order (no doc change);
   (b) narrow amendment — Owner-only „отключване" в кратък прозорец (напр. 24 ч)
   само за погрешно приключване, timeline-logged (amends 01 BR-2 + 02 matrix).
   PO decision required before Етап 2 implements closure.
4. Identity: тънък срез в Етап 2 (login/PIN/seeded Owner), пълна администрация в
   Етап 3 — BR-5 запазен.
5. Gate discipline (PO-confirmed): локалният PASS не замества VM докладите;
   ADR-002 се затваря само след тях; Етап 2 стартира с миграция №1 след това.
6. AI: нищо преди основният поток да работи отлично (PO директива).

## Out of scope — unchanged

Everything in 00 §Roadmap V1.5+ · SaaS beyond C1–C8 · configuration UIs seed data
covers. "Seemed easier while coding" is not a rationale (07).
