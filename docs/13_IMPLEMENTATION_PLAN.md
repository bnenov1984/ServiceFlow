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

**Backend: ✅ done (migrations #1–#6, commits 31b2038…24a9e40).** Frontend not
started — gated (see below).

- Migration #1: companies, users, sessions **+ RLS policies + scoped-query
  chokepoint (ADR-016)**; login/PIN, seeded Owner **per dev/staging tenant** (self-
  serve registration idва в Етап 3 — dev/pilot tenants се създават by hand). ✅
- Isolation tests entered the P0 list (P0-9), growing with every migration:
  customers, assets, orders, tasks, attachments, contacts all proven cross-tenant
  isolated (incl. a real RLS-bypass bug found and closed — ADR-016 §finding). ✅
- Migrations #2–#6, all ✅: клиенти (normalization + duplicate hint) · активи
  (seeded typed asset types + identifier extraction) · поръчки + статуси + пълна
  матрица (P0-1, exhaustively tested) · диагноза (in-place, approval persists to
  the record) · part/labor lines + accessories (BR-3 derived totals) · задачи
  (извън агрегата, per докс/01 §4) · attachments (storage port ADR-007, local fs
  adapter, mandatory image re-encoding + HEIC support, thumbnails) · contact
  records (+ „note" type extension за бележки) · timeline с actor attribution,
  append-only на ниво база (trigger) · **минимален приемо-предавателен протокол**
  (server-side PDF, fpdf2 + DejaVu Sans за кирилица) · BR-2 unlock изключението.
  81/81 backend tests green; ruff/mypy/import-linter clean throughout.
- **Not yet built (backend):** global search (P0-7) — postponed, no consumer
  until the frontend needs it; will land alongside the Kanban/dashboard work.
- **Frontend gate (PO директива, 11.07.2026) — BLOCKS everything below:**
  преди какъвто и да е frontend код се изработва отделен **Frontend Design
  Document** (детайлизира 10: компонентна йерархия, състояния, data-fetching
  контракти към 09, дизайн токени, responsive поведение, error/loading/empty
  състояния per екран) и се одобрява от PO. Frontend-ът се пише само срещу него.
- Exit (still open): four screens built against the design doc · search wired in
  · E2E journeys 1, 2, 4 green (вкл. protocol print snapshot + isolation suite) ·
  non-developer completes intake→close unassisted **в браузър срещу staging**.

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
