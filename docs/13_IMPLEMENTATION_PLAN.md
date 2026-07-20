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

**Плащания (Payment recording) — ✅ landed 19.07.2026, ahead of the rest of
Етап 4.** `serviceflow.commercial` (migration #8: `payments`, RLS FORCE +
tenant_isolation) · `POST /orders/{id}/payments` · derived `paid_amount`/
`balance` on order detail (BR-3, reuses `lines.order_totals` — no second money
formula) · refund = new offsetting record, never a mutation · allowed on
terminal orders (docs/01 §ServiceOrder exception), blocked only when archived
· DeliveryDialog records an optional payment inline, delivery still succeeds
with an open balance · `payment_recorded`/`payment_refunded` timeline events.
Chosen ahead of Фактура because it needs no numbering, no accountant-reviewed
VAT rules, and docs/08 already declares `payments.invoice_id` nullable — it
never required Invoice to exist.

**Architecture boundary repair — ✅ landed 20.07.2026.** The Payment slice had
created a commercial ↔ service_orders import cycle (BOS-09 risk R-3
materializing). `service_orders/contracts.py` and `commercial/contracts.py`
now carry the only sanctioned cross-module surface (docs/business-os/04 rule
R4, now Enforced via two `backend/.importlinter` `protected` contracts);
service_orders' `paid_amount`/`balance` need is met by a
`PaymentSummaryProvider` port it owns and commercial implements, wired by the
composition root — never a direct import either way.

**Фактура (Invoice) — Draft slice ✅ landed 20.07.2026**, using the repaired
contract: `POST /orders/{id}/invoices` creates a draft prefilled from the
order's part/labor lines via `service_orders.contracts.get_order_lines`
(never `.models`/`.lines` directly) · `GET /invoices`, `GET /invoices/{id}`,
`PATCH /invoices/{id}` (drafts only, replaces the line set) · migration #9:
`invoices`/`invoice_lines`, full docs/08 column set (so no future ALTER TABLE
is needed) but every row this slice creates stays `status="draft"` — number,
seller/buyer snapshot, net/vat/gross, pdf_storage_key all stay NULL · also
adds the `fk_payments_invoice_id_invoices` constraint migration #8 deferred.
**Invoice issue/annul/reissue/PDF/VAT remain not started**: numbering
ownership (`document_sequences` — still the one Open item, BOS-05 §1),
accountant review, VAT modes, immutability, PDF, annul/reissue.

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
