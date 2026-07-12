# 13 — Implementation Plan

Status: **v3.0 — web-first SaaS restage after the 11.07.2026 pivot (doc 14)**;
carries the PO stage philosophy of v2.1 (core flow → administration → commercial
documents → hardening). Planned for one developer; every stage ends runnable.
BR-2 amendment (reopen rule + Owner unlock) included in Етап 2.

## Етап 0 — Foundation ✅ (revalidated for SaaS)

Done and kept: repo, module skeleton + import contracts, CI, health scaffold,
i18n pattern, frontend skeleton. **The ADR-002 VM gate is void — migration #1 is
unblocked.** Local-edition artifacts parked in `ops/local-edition/`.
Remaining Етап-0 items (small): dev docker-compose already exists; staging/prod
host provisioning moves to Етап 3 (nothing before it needs a public host).

## Етап 1 — Замразяване ✅ (amended by doc 14)

Frozen set unchanged except the platform layer: ADR-016/017/018 join; 002/005/
009/014 superseded-or-parked. Domain/workflow/schema/API/UI untouched by the pivot.

## Етап 2 — Core MVP (Клиент → Поръчка → Актив → Задачи → Статуси → Бележки → Приключване) — ~9–11 weeks

Unchanged from v2.1 **plus tenant enforcement from the first migration**:

- Migration #1: companies, users, sessions **+ RLS policies + scoped-query
  chokepoint (ADR-016)**; login/PIN, seeded Owner **per dev/staging tenant** (self-
  serve registration idва в Етап 3 — dev/pilot tenants се създават by hand).
- Isolation tests enter the P0 list now (P0-9): A не вижда B — customers, orders,
  search, attachments, jobs.
- Всичко останало от v2.1: клиенти · активи · поръчки · статуси + матрица (P0-1)
  · задачи · бележки · диагноза · part/labor lines as data (P0-3) · аксесоари ·
  attachments (S3 adapter на порта; local fs за dev) · contact records · timeline
  с actor attribution · търсене (P0-7) · приключване + BR-2 unlock изключението ·
  **минимален приемо-предавателен протокол** · четирите екрана.
- **Frontend gate (PO директива, 11.07.2026):** преди какъвто и да е frontend код
  се изработва отделен **Frontend Design Document** (детайлизира 10: компонентна
  йерархия, състояния, data-fetching контракти към 09, дизайн токени, responsive
  поведение, error/loading/empty състояния per екран) и се одобрява от PO.
  Frontend-ът се пише само срещу него.
- Exit: E2E journeys 1, 2, 4 green (вкл. protocol print snapshot + isolation
  suite); non-developer completes intake→close unassisted **в браузър срещу
  staging**.

## Етап 3 — SaaS Shell & Administration — ~6–8 weeks

- **Hosting + CD (ADR-017):** EU host, staging + production, GitHub Actions
  pipeline, managed PostgreSQL + tested restores, S3 storage, TLS.
- **Регистрация и onboarding:** company self-registration, email verification,
  ≤3-стъпков wizard, «Зареди примерни данни» demo seeding.
- **Абонаменти и billing (ADR-018):** 14-дневен trial без карта, един месечен
  план, provider adapter + webhook inbox (P0-10: webhook idempotency), dunning,
  read-only + export degradation.
- **Администрация (tenant):** users/roles UI (invite/deactivate, progressive
  disclosure), settings (фирмени данни, статуси rename/toggle, warranty defaults).
- **Платформена админ конзола (vendor):** companies + subscriptions overview,
  extend/suspend/override с причина, audit.
- **Диагностика:** health endpoint → uptime мониторинг + error tracking; tenant
  export artifact (ADR-012 — GDPR + бъдеща локална едиция).

## Етап 4 — Commercial Documents — ~4–5 weeks + счетоводен gate

Unchanged from v2.1: диагностична оферта към поръчка · разширени протоколи ·
фактури (P0-2 gapless) · плащания · **счетоводен gate**.

## Етап 5 — Hardening & Pilot

Security hardening по преработения 11 (internet-facing: rate limiting навсякъде,
security headers, dependency watch, backup restore drill на хоста) · performance
budget (10 §9) · recovery drill: възстановяване на цял хост от бекъпи < 2 h
(ADR-017) · **пилот: реален сервиз ≥2 седмици върху production** · обратна връзка
· release readiness: P0 green (сега 10 позиции) · счетоводен sign-off · правен
преглед (условия + privacy за публичен SaaS — **нов, задължителен за публичен
launch**).

## P0 additions (doc 12 §1 extended by the pivot)

- P0-9 tenant isolation suite (ADR-016)
- P0-10 billing webhook idempotency (ADR-018)

## Reconciliation notes (v2.1 → v3.0)

1. VM gate void; миграция №1 отключена веднага (доc 14).
2. Registration/billing/admin консолидирани в Етап 3 (замества installer/updater/
   licensing реда; той е паркиран за локалната едиция).
3. Етап 2 добавя само tenant enforcement — иначе идентичен на v2.1.
4. Правен преглед на публични условия/privacy добавен като launch gate (нов факт
   от pivot-а: публичен SaaS = публични правни документи).
5. Carried billing решения от 10.07 (doc 14 §Carried) важат до вето.
