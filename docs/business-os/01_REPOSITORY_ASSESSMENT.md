# BOS-01 — Repository Assessment

Status: **Phase 0 discovery — describes the repository as it actually is** ·
Date: 17.07.2026 · Basis: direct inspection at commit `6c324ff` (main). Everything
in this document is *existing implemented behavior* or *existing documented
decision* unless explicitly marked otherwise.

## 1. Architectural style

**Modular monolith, mechanically enforced.** One FastAPI application
([backend/src/serviceflow/main.py](../../backend/src/serviceflow/main.py))
assembles per-module routers; module boundaries are enforced in CI by
import-linter ([backend/.importlinter](../../backend/.importlinter), run as
`uv run lint-imports` in [.github/workflows/ci.yml](../../.github/workflows/ci.yml)).
Decided in [ADR-001](../adr/ADR-001-modular-monolith.md); module map in
docs/03 §5.

**Deployment model: web-first multi-tenant SaaS** since the 11.07.2026 pivot
([14_WEB_FIRST_PIVOT.md](../14_WEB_FIRST_PIVOT.md), ADR-016/017/018). The local
Windows edition is parked, not deleted: installer + PostgreSQL-bundling spike
live in [ops/local-edition/](../../ops/local-edition/), and ADR-002/005/009/014
are marked superseded-or-parked in [07_ADR_INDEX.md](../07_ADR_INDEX.md).

> ⚠️ **Conflict with the Phase 0 task brief.** The brief's deployment section
> assumes "local Windows installation, LAN browser access, one company per
> installation, offline daily operation". That describes the **parked** local
> edition (docs/03 §5 picture, docs/04–06). The repository's authoritative
> current direction is web-first SaaS: docs/14 (PO decision 11.07.2026),
> docs/07 pivot amendment, docs/13 v3.0, CLAUDE.md ("Web-first multi-tenant
> SaaS … local edition parked as a future option"), and implemented RLS
> enforcement. **Recommendation:** docs/14 remains authoritative; Business OS
> treats "local edition" as a second deployment target of the same artifact
> (see [07_DEPLOYMENT_MODEL.md](07_DEPLOYMENT_MODEL.md)), not as the baseline.
> Similarly, the brief's "do not introduce multi-tenancy unless requirements
> demand it" is moot: multi-tenancy is already implemented and P0-tested
> (ADR-016, `backend/tests/test_isolation.py`).

## 2. Backend layout (all paths under `backend/src/serviceflow/`)

| Package | Contents (files, not inferred) | Role |
|---|---|---|
| `shared_kernel/` | `db.py` (Base, naming conventions, TimestampMixin, `TenantContext`, `scoped()` chokepoint, RLS GUC binding + re-begin/checkin hooks), `ids.py` (UUIDv7 `new_id`), `events.py` (in-proc `DomainEvent`/`publish`/`subscribe`), `normalize.py` (Cyrillic/phone normalization), `storage.py` (`StoragePort` Protocol + content-addressed local FS adapter) | Bottom layer; imports nothing above it (enforced) |
| `identity/` | `models.py` (Company, User, AuthSession, AuditLog), `service.py`, `security.py`, `router.py` (auth + users), `deps.py` (`get_tenant` — "the only constructor of tenant scope", `get_tenant_db`, `require_csrf`, `require_owner`) | Tenant bootstrap; identity tables exempt from RLS, queries centralized |
| `customers/` | Customer model with ADR-010 shadow columns, GDPR anonymization | Domain |
| `assets/` | AssetType (seeded), Asset, AssetIdentifier | Domain |
| `service_orders/` | ServiceOrder aggregate: `models.py` (OrderStatus, DocumentSequence, ServiceOrder, Diagnosis, PartLine, LaborLine, AccessoryItem), `statuses.py` (transition matrix), `lines.py`, `protocol.py` (fpdf2 PDF), `router.py`, `service.py` | Domain (the center) |
| `tasks/` | Task (`order_id` nullable — outside the aggregate per docs/01 §4) | Domain |
| `contacts/` | ContactRecord (call/email/message/visit/note) | Domain |
| `attachments/` | Attachment model, `media.py` (re-encode, HEIC, thumbnails), storage-port consumer | Domain |
| `timeline/` | TimelineEvent (append-only, DB trigger), `service.py` subscribes to domain events (ADR-011) | Domain (observer) |
| `search/` | Router + service querying customers/assets/orders (read-only cross-module reads — sanctioned by docs/03 §5) | Domain (observer) |
| `dashboard/` | `router.py` only — aggregating read queries | Domain (read model) |
| `commercial/` | **Empty (`__init__.py` only).** Reserved for Invoice/Payment/sequences per docs/08 §commercial, built in Етап 4 | Placeholder |
| `platform/` | `health.py` only (health endpoint). docs/03 assigns it license/backup/updater/jobs — SaaS pivot moves most of that to Етап 3 | Platform |
| top level | `main.py` (app factory, error envelope per docs/09 §1), `config.py`, `logging_setup.py`, `seed.py` | Composition root |

**Application-service style:** each module is `models.py` + `service.py` +
`router.py`. No repository layer, no CQRS, no DI container — plain functions
taking a `Session` + `TenantContext`. Persistence is SQLAlchemy 2.0 declarative +
Alembic ([backend/migrations/versions/](../../backend/migrations/versions/),
0001–0006).

## 3. Tenancy, auth, authorization (implemented)

- Session cookie → `identity/deps.py::get_auth` → `TenantContext` (company_id,
  user_id, is_owner) — never from client input (ADR-016).
- Every tenant-table query goes through `shared_kernel.db.scoped()`; RLS with
  `FORCE` + fail-closed GUC on every tenant table (migrations 0002+); GUC is
  re-applied on transaction re-begin and reset on pool check-in (real bug found
  and closed — documented in `db.py` docstring and ADR-016).
- Authorization is deliberately minimal: one `is_owner` boolean, `require_owner`
  dependency. No roles/permissions tables (docs/08 §4 "deliberately absent").
- `audit_log` records technical events (logins, PIN switches, admin actions);
  business history goes to the timeline — the split is a documented rule
  (`identity/models.py::AuditLog` docstring, docs/11 §2).

## 4. Database ownership (implemented)

21 tables across migrations 0001–0006, every one with UUIDv7 `id` and (except
global seeds `order_statuses`) `company_id` (ADR-013). Full matrix with owners:
[05_DATA_OWNERSHIP.md](05_DATA_OWNERSHIP.md). One schema, one database, one app
role (non-superuser so RLS binds — CLAUDE.md hard rule 2).

## 5. Frontend layout (`frontend/src/`)

React 18 + TS + Vite + Tailwind + TanStack Query (ADR-004), built against the
approved Frontend Design Document (docs/15). Feature folders mirror backend
modules: `auth/`, `customers/`, `intake/`, `orders/` (Kanban), `order/`,
`dashboard/`, `shell/`, plus `components/` (shared UI), `lib/api.ts` (single
fetch wrapper: cookies, CSRF header, docs/09 §1 error envelope),
`i18n/bg.ts` (single flat catalog — hard rule 4), and `generated/` (openapi.json,
`api.d.ts`, `transition-matrix.json` exported from the backend by
`backend/scripts/`). **The frontend is one app with no module boundaries** — no
lint enforcement equivalent to `.importlinter` exists there.

## 6. Tests, CI, quality gates

- `backend/tests/` — 17 files; per docs/13, 81/81 green at the Етап-2 backend
  finish line, ruff/mypy/import-linter clean. Includes `test_isolation.py`
  (P0-9 cross-tenant isolation, grown with every migration).
- CI (< 10 min budget, docs/12 §4): backend job vs real PostgreSQL 16 (ruff,
  mypy, lint-imports, pytest), frontend job (vitest + build).
- P0 list docs/12 §1 (10 items after the pivot) is the release gate
  (CLAUDE.md hard rule 8).

## 7. Local-first assumptions still in the codebase

- `shared_kernel/storage.py` local-FS adapter is the only storage adapter (S3
  adapter is Етап 3 work — planned, not present).
- `ops/local-edition/` (installer, spike) — parked by design.
- PIN fast-switching (ADR-008) assumes a shared counter device — kept in SaaS.
- No local-edition assumption remains in the domain modules; that separation is
  what docs/14 relied on.

## 8. Coupling observations (evidence for later documents)

1. **`shared_kernel.events.DomainEvent` has an `order_id` field** — a ServiceFlow
   concept in the bottom, supposedly domain-neutral layer
   ([events.py:20](../../backend/src/serviceflow/shared_kernel/events.py)).
   Smallest real Core leak found.
2. **`timeline_events.order_id` is NOT NULL with FK to `service_orders`** — the
   timeline is an order history, not a generic activity feed.
3. **Cross-module FKs to `service_orders.id`** from tasks, attachments,
   contact_records, and to `customers.id`/`assets.id` from service_orders.
   Normal inside one product; the extraction cost if any of these modules is
   ever shared.
4. **`document_sequences` lives in `service_orders/models.py`** though it is
   named and shaped generically (kind, year, current) and docs/08 files it under
   `commercial`. Doc-vs-code placement mismatch (see §9).
5. **`search/` and `dashboard/` read other modules' models directly** —
   explicitly sanctioned today (docs/03 §5 "search … read-only access across
   modules"), but it is the pattern that must become query contracts at any
   future module boundary.
6. **Frontend has a single i18n catalog and a single API client** with no
   per-module namespacing enforcement (keys are in practice prefixed:
   `orders.*`, `customers.*`, …).
7. `.importlinter` has only two contracts (domain↛platform,
   shared_kernel-bottom); domain modules are **not yet independent of each
   other** by rule — the file itself notes "Finer independence contracts tighten
   in Stage 1".

## 9. Doc-vs-code conflicts found

| # | Conflict | Locations | Recommendation |
|---|---|---|---|
| 1 | Task brief assumes local-first deployment; repo is web-first SaaS | Brief §7 vs docs/14, docs/07 amendment, CLAUDE.md | docs/14 authoritative (see §1 note). **Recommended** |
| 2 | `document_sequences` table: docs/08 §2 files it under `commercial`; code defines it in `service_orders/models.py` (used for order numbers today; invoices come in Етап 4) | [08_DATABASE_DESIGN.md](../08_DATABASE_DESIGN.md) §commercial vs [service_orders/models.py](../../backend/src/serviceflow/service_orders/models.py) | Keep code as-is now (Етап 4 will consume it); record ownership as **Open** in 05 — either commercial takes the table over in Етап 4, or docs/08 is amended to file it under service_orders. Do not move code in Phase 0. |
| 3 | docs/03 §5 assigns `platform/` license/backup/updater/jobs; code has only `health.py`, and the pivot reassigned that scope (billing, CD) | docs/03 §5 vs `platform/` contents + docs/14 | Not a live conflict — docs/03 predates the pivot and docs/07 records the amendment chain. No action. |
| 4 | docs/08 §4 says "no tenant RLS locally (SaaS adds enforcement)"; RLS is now implemented everywhere | docs/08 §4 vs migrations 0002+ | docs/08 §4 sentence is stale post-pivot; ADR-016 governs. Recommend a one-line amendment to 08 when it is next touched (07 change process). **Non-blocking.** |

## 10. Areas already suitable for extraction vs not

- **Already domain-neutral in behavior and naming:** `shared_kernel/ids.py`,
  `db.py`, `storage.py`, `normalize.py`; `identity/` (nothing repair-specific in
  it); `platform/health.py`. These are the de-facto Core.
- **Neutral behavior, ServiceFlow anchoring:** events bus (order_id field),
  attachments (order FK), tasks (order FK, nullable), document_sequences
  (location), contact records (customer+order FKs). Isolate, don't extract —
  see [02_DOMAIN_CLASSIFICATION.md](02_DOMAIN_CLASSIFICATION.md).
- **ServiceFlow to the bone:** customers-as-modeled (phone-first, translit
  shadow columns), assets, the ServiceOrder aggregate, statuses/transition
  matrix, diagnosis, protocol PDF, timeline, intake/Kanban/dashboard UI.
