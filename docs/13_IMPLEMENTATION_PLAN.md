# 13 — Implementation Plan

Status: **v3.0 — web-first SaaS restage after the 11.07.2026 pivot (doc 14)**;
carries the PO stage philosophy of v2.1 (core flow → administration → commercial
documents → hardening). Planned for one developer; every stage ends runnable.
BR-2 amendment (reopen rule + Owner unlock) included in Етап 2. **Étап 3's
vendor/tenant administration bullets cross-referenced 26.07.2026** to
ADR-BOS-009…012 and
[business-os/18_VENDOR_TENANT_ADMINISTRATION.md](business-os/18_VENDOR_TENANT_ADMINISTRATION.md)
(audit-driven ownership model; documentation only, no stage timeline change).

## Repo-Wide Status (authoritative)

This block is the single current-status source for the whole repository.
`docs/business-os/08_EVOLUTION_ROADMAP.md` and any acceptance-checklist
snapshot (e.g. `docs/business-os/19_MVP_ACCEPTANCE_CHECKLIST.md`) describe
plans or point-in-time verification, not current status — they defer to
this block.

| Field | Value |
|---|---|
| Platform/repository stage | Етап 3 (SaaS Shell & Administration) — core administration/onboarding/Vendor Control Plane implemented, billing still V1 manual-vendor-driven; Етап 4 (Commercial Documents) — draft/issue/annul/PDF/VAT-modes all landed, reissue and credit/debit notes explicitly deferred. Neither stage's exit checklist has been formally closed; Етап 5 (Hardening & Pilot) is the realistic next stage of new work. |
| BusinessOS phase | Phase 4.5 — Vendor Control Plane & RepairFlow business profiles (docs/business-os/08_EVOLUTION_ROADMAP.md, amended 26.07.2026) |
| Active vertical/module | RepairFlow (core) — active development, frontend built out well past the original Etap 2 gate (intake, Kanban board, delivery, invoices, vehicle/service history, warranty settings, employee admin, password reset); Professional Services — implemented; Construction Supervision — planned only, no backend |
| Current focus | Closing out Etap 4 loose ends (the accountant sign-off gate — see the row below; it needs a human accountant, not more engineering) and broadening E2E coverage before moving into Etap 5 hardening |
| Deployment state | Live on Render (frontend + backend), backed by Neon PostgreSQL; cross-origin CORS and session-cookie configuration in place for the split-origin setup |
| Test suite (re-verified 2026-09-20) | Backend: 750 tests collected (`uv run pytest --collect-only`), up from 364 on 2026-08-02. Frontend: **506/506 vitest cases green** (50 files), up from 162. `uv run ruff check .` clean · `uv run mypy` clean (101 files) · `uv run lint-imports`: 9/9 contracts kept, 0 broken. The DB-backed pytest run was **not** repeated on 09-20 (no local Postgres); last known green in CI on `main` at cf6cb13, with no source commits since. |
| **Open release gate — accountant sign-off** | Reconciled 20.09.2026: the code and `docs/ACCOUNTANT_REVIEW.md` **do** agree — §4 records the B2B/company-buyer Issue slice landing 09.08.2026, and its Phase-A scope table matches `commercial/service.py`'s `_buyer_snapshot()` (individuals; domestic companies with a known `vat_registered` state; `buyer_vat_status_unknown` rejected before number allocation). The earlier framing of this row — that the doc lagged the code — was wrong. What remains is not an engineering reconciliation but the gate itself: no qualified Bulgarian accountant has recorded a dated answer to the open `PROFESSIONAL REVIEW REQUIRED` items (B2 individual-buyer field completeness incl. the national-ID question, T1 seller-field completeness, VAT rounding, control adequacy). docs/12 §4 makes that sign-off a release gate for anything touching `commercial`, so Etap 4 cannot be called done until a human accountant signs. |
| Last reviewed | 2026-09-20 |

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

**Backend: ✅ done (migrations #1–#6, commits 31b2038…24a9e40).** Frontend:
✅ built and shipped past the original gate (see below) — the "not started"
phrasing here is historical, not current.

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
- **Global search (P0-7) — ✅ built, correcting this file (20.09.2026).** The
  2026-09-12 refresh claimed it was "not yet built"; that was wrong, and this
  bullet is the correction. `serviceflow/search/` (`service.py` + `router.py`,
  grouped customers/orders/assets hits, normalization symmetric with the write
  path per ADR-010) is mounted at `GET /api/v1/search` in `main.py`, and the
  frontend consumes it from `shell/SearchBox.tsx` (debounced, keyboard-
  navigable, highlighted) inside RepairFlow's toolbar in `AppShell.tsx`. It
  shipped in 6ecb4a0 alongside `GET /users` and `/dashboard`. P0-7 coverage
  lives in `backend/tests/test_frontend_prerequisites.py` (both alphabets,
  phone/identifier/order-number forms, short-query floor, tenant isolation).
  Remaining gaps, both small: no `SearchBox.tsx` unit test and no E2E.
- **Frontend gate (PO директива, 11.07.2026) — cleared.** The Frontend Design
  Document gate was passed some time before this review; the frontend has
  since been built well past the original four-screen scope (order intake,
  Kanban board (`orders/KanbanBoard.tsx`), delivery dialog, invoice
  draft/issue/annul views, vehicle identity/service history, warranty
  settings, employee admin, password reset/forgot-password). This bullet is
  kept only as a historical note — do not treat it as a live blocker.
- Exit checklist, actual state (20.09.2026): four+ screens built and shipped ·
  Kanban wired in · search (P0-7) **is** wired in, backend and frontend (the
  09-12 entry said otherwise; corrected above) · E2E coverage exists for
  journeys 1 (intake→delivery, via `e2e/repairflow/order-intake.spec.ts` +
  `order-delivery.spec.ts`), 3 (invoice lifecycle, draft→issue only, via
  `order-invoice.spec.ts`) and 2's first half (rejection to a terminal state,
  via `order-rejection.spec.ts`, cf6cb13 — the такса диагностика invoice +
  плащане leg is still uncovered), plus `e2e/auth.spec.ts`/
  `e2e/repairflow/order-intake-customer.spec.ts`/`order-status.spec.ts`
  (`repairflow/` materialized 2026-09-12, per `frontend/e2e/CLAUDE.md`);
  journey 4 (Kanban concurrency — though the race-condition fix d02e051
  hardened this ad hoc) still has no dedicated spec · non-developer unassisted
  staging walkthrough not confirmed in this review. This checklist was never formally closed out
  when the gate was passed — worth a deliberate close rather than leaving it
  implicitly done.

## Етап 3 — SaaS Shell & Administration — ~6–8 weeks

- **Hosting + CD (ADR-017):** EU host, staging + production, GitHub Actions
  pipeline, managed PostgreSQL + tested restores, S3 storage, TLS.
- **Регистрация и onboarding:** company self-registration, email verification,
  ≤3-стъпков wizard, «Зареди примерни данни» demo seeding.
- **Абонаменти и billing (ADR-018):** 14-дневен trial без карта, един месечен
  план, provider adapter + webhook inbox (P0-10: webhook idempotency), dunning,
  read-only + export degradation. **V1 landing (26.07.2026 audit,
  ADR-BOS-012):** същите състояния, преходи задвижвани ръчно от vendor admin
  вместо от webhook, докато provider интеграцията (по-горе) не е готова —
  вижте [business-os/18](business-os/18_VENDOR_TENANT_ADMINISTRATION.md) §9
  workstream 4.
- **Администрация (tenant):** users/roles UI (invite/deactivate, progressive
  disclosure, ограничено от vendor-зададен seat limit — ADR-BOS-009), settings
  (фирмени данни, статуси rename/toggle, warranty defaults, workflow
  templates — всичко това **в рамките на назначения RepairFlow business
  profile**). Самият profile се показва **read-only** с „заявка за промяна"
  — назначава се от vendor при provisioning и се сменя само по контролиран
  път (ADR-BOS-011, PO уточнение 26.07.2026); не е нито entitlement, нито
  обикновена tenant настройка.
- **Платформена админ конзола (vendor):** companies + subscriptions overview,
  provisioning (компания + първи Owner + начален business profile),
  entitlements, seat limits, extend/suspend/override с причина, audit.
  Ролята "vendor admin" е структурно отделна от `users`/`is_owner` (никога
  слята с tenant ролите), а видимостта е **metadata-first**: vendor вижда
  административни данни за тенанта (идентичност, абонамент, приложения,
  seats, profile, suspension, health/version, вътрешни бележки, platform
  audit), но **не** оперативните данни на клиента (клиенти, активи, поръчки,
  ангажименти, документи, фактури, бележки) — само агрегирани броеве.
  Пълен модел, ownership matrix и предложени схеми:
  [ADR-BOS-009](adr/ADR-BOS-009-vendor-control-plane-vs-tenant-workspace.md)
  (vendor vs tenant разделение),
  [ADR-BOS-010](adr/ADR-BOS-010-application-entitlement-ownership.md)
  (activation/entitlement собственост),
  [business-os/18](business-os/18_VENDOR_TENANT_ADMINISTRATION.md) (одит +
  V1 обхват на конзолата, §7).
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
**Update, 2026-09-12: issue/annul/PDF/VAT modes have since landed** (this
paragraph's "remain not started" line is stale and kept below only for
history). Confirmed in code: `commercial/router.py`/`service.py` implement
`POST /invoices/{id}/issue` (gapless numbering via `next_invoice_number()`,
issued-immutability), `POST /invoices/{id}/annul`, on-demand PDF rendering
(`commercial/pdf.py`, fpdf2, not stored — `pdf_storage_key` stays unset by
design), and both VAT modes (`vat_mode="registered"` at 20% ROUND_HALF_UP,
`"not_registered"` at 0). **Reissue is deliberately not built**: annul + a
separate new manual invoice is the current workaround; linked
reissue/credit-debit-notes are a distinct, later slice, not retrofitted onto
`annuls_invoice_id`. Numbering ownership (`document_sequences`, BOS-05 §1)
resolved in favor of `service_orders` keeping the table, per the original
options. **See the accountant sign-off reconciliation note in the Repo-Wide
Status block above before treating this stage as done** — the accountant
review doc and the current code's buyer-type coverage may have diverged.

<details>
<summary>Original (2026-08-24) note, superseded above</summary>

Invoice issue/annul/reissue/PDF/VAT remain not started: numbering
ownership (`document_sequences` — still the one Open item, BOS-05 §1),
accountant review, VAT modes, immutability, PDF, annul/reissue.

</details>

**Central invoice workspace ("Фактури") ✅ landed 09.08.2026.** RepairFlow's
`/invoices` nav item, previously grayed, is now a real page: `GET /invoices`
gained `limit`/`offset` (query-level pagination, default 50) and a richer
`InvoiceListItemOut` per row (order_number, customer_name, total), batch-
enriched via new `service_orders.contracts.get_order_summaries` and
`customers.contracts.get_customer_summaries` — no per-row query. A history/
list view only; invoices are still created exclusively from a Service
Order's own Invoice section. At landing, "Отвори" reused the existing
`/orders/{id}` + InvoiceCard — corrected below.

**Standalone Invoice Detail (`/invoices/{id}`) ✅ landed 09.08.2026.** UX
correction: the central list's "Отвори" was navigating to the originating
Order, which contradicted an Invoice workspace's own natural "open the
invoice" expectation. Now "Отвори" opens `/invoices/{id}`
(invoices/InvoiceDetailPage.tsx); the Order number remains its own separate
link to `/orders/{order_id}`. `InvoiceDraftEditor`/`IssuedInvoiceView` were
extracted out of `order/InvoiceCard.tsx` into their own files so both the
order-centric and invoice-centric views render the exact same components
against the same `queryKeys.invoice(id)` cache — no second Invoice UI.

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

**Unreconciled (flagged 20.09.2026, PO decision needed — not actioned here):**
Етап 5 above counts "P0 green (сега 10 позиции)" as the frozen doc 12 §1 list
of 8 plus these two. But doc 12 §1's **P0-5 (updater kill-the-process drills on
a Windows reference VM)** describes machinery the pivot parked: ADR-014
(owner-triggered updates) is superseded by ADR-017's vendor-operated CD, so
there is no updater to drill. **P0-4 (backup → verify → restore drills)**
survives in substance but has moved target — Етап 5 already restates it as a
host-level restore drill (<2 h, ADR-017), not the 05 §7 local-instance drill.
Doc 14 §"What is superseded / parked" never touched the P0 list (it says only
that "all P0 tests survive"), and doc 12 is frozen, so the release gate as
written today counts at least one item nobody can satisfy. Either amend doc 12
§1 through the change process (doc 07 §"Change process after freeze") or
restate the web-first P0 list here as the authoritative one.

## Reconciliation notes (v2.1 → v3.0)

1. VM gate void; миграция №1 отключена веднага (доc 14).
2. Registration/billing/admin консолидирани в Етап 3 (замества installer/updater/
   licensing реда; той е паркиран за локалната едиция).
3. Етап 2 добавя само tenant enforcement — иначе идентичен на v2.1.
4. Правен преглед на публични условия/privacy добавен като launch gate (нов факт
   от pivot-а: публичен SaaS = публични правни документи).
5. Carried billing решения от 10.07 (doc 14 §Carried) важат до вето.
