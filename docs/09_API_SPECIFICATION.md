# 09 — API Specification

Status: **Approved by Product Owner 10.07.2026** · Date: 10.07.2026 · Basis: 02, 08, ADR-003/008
Contract style, conventions and the endpoint surface. Freezes at implementation
start; the generated OpenAPI schema becomes the machine-readable source of truth.

## 1. Conventions

- Base path `/api/v1`, JSON only. The SPA is served by the same process (ADR-004).
- **Auth:** session cookie (HttpOnly) + `X-CSRF-Token` header on mutations; PIN
  switch swaps the acting identity within a device session (ADR-008). Every mutation
  records the acting user.
- **Errors:** `{code, message_key, params, field_errors?}` — `message_key` is an
  i18n catalog key (ADR-015); the API never returns prose. HTTP: 400 validation ·
  401 no session · 403 role/PIN required · 404 not in this company · 409 conflict
  (row_version or state) · 423 read-only mode (license, ADR-009).
- **Concurrency:** user-edited aggregates require `row_version`; mismatch → 409 with
  a refetch hint (Kanban conflict toast, 02 §16).
- **Pagination:** cursor-based `?limit&cursor`; lists default to non-archived.
- **Idempotency:** unsafe creates accept `Idempotency-Key` (double-click protection).

## 2. Endpoint surface (method — path — notes)

### Auth & identity
- POST /auth/login · POST /auth/logout · POST /auth/pin-switch (user_id + PIN)
- GET /auth/me — acting user, role, license mode
- GET|POST|PATCH /users · POST /users/{id}/deactivate — Owner only

### Customers & assets
- GET /customers (search, includes duplicate-phone hint) · POST /customers
- GET /customers/{id} — profile: details, orders, assets, recent activity
- PATCH /customers/{id} · POST /customers/{id}/archive · POST /customers/{id}/anonymize (Owner, GDPR)
- GET|POST /customers/{id}/assets · PATCH /assets/{id} · POST /assets/{id}/archive
- GET /asset-types — seeded definitions for form rendering
- POST /assets/{id}/reveal-sensitive — audited (BR-10)

### Service orders
- POST /orders — intake payload (find-or-create customer + asset inline, 02 §3)
- GET /orders — filters: status, technician, overdue, priority, q
- GET /orders/{id} — full detail (lines, diagnosis, accessories, adjustments, timeline page 1)
- PATCH /orders/{id} — fields per edit rules (row_version)
- POST /orders/{id}/status — {to, reason?, approval?} — the **only** way any client
  (incl. Kanban DnD) changes status; server enforces the matrix (02 §2)
- POST /orders/{id}/archive (terminal only) · POST /orders/{id}/warranty-return —
  creates linked order
- GET /orders/{id}/protocol.pdf — intake/delivery variants (?type=)
- CRUD nested, flat paths: /orders/{id}/diagnosis (PUT — single record),
  /part-lines, /labor-lines (order-workflow-revamp WP-I, Q12a/Q13d: created
  only from a `catalog_item_id`, no name/price field; only while the order is
  in Диагностика/Чака клиент/Чака части/Ремонт), /accessories (per-asset-type
  gated, 01 BR-9), /adjustments (WP-I, Q13: Owner-only, append-only, resolves
  01 OQ-5), /contact-records
- PATCH /part-lines/{id} — incl. state changes among издадена/поръчана/
  монтирана *(WP-J, Q15/Q15b — adding a line via POST only accepts издадена or
  поръчана as the starting state, "installed" only via this PATCH)*; also
  `has_warranty` (boolean, WP-J Q14 — no `warranty_months`/`warranty_days`
  field any more); no name/price field (WP-I). A response to POST or a
  state-changing PATCH may carry `suggested_status` (WP-J, Q5/Q5c) — a
  one-click nudge the client still has to confirm via its own
  POST /orders/{id}/status call, never an automatic transition.
- POST /orders/{id}/attachments (multipart) · GET /attachments/{id}/file — authorized
  stream (ADR-007), ?thumb= for photos · DELETE — soft
- GET /orders/{id}/timeline — paged, read-only

### Catalog *(order-workflow-revamp WP-I, ADR-BOS-013)*
- GET /catalog-items (?kind=, ?include_archived=) — open to any active user
  (the line picker needs it); `unit_cost` only populated for an Owner caller
- POST /catalog-items · PATCH /catalog-items/{id} · POST /catalog-items/{id}/archive
  · POST /catalog-items/{id}/unarchive — Owner-only; items are archived, never
  deleted (lines keep a reference)
- POST /catalog-items/import/preview · POST /catalog-items/import/commit
  (multipart file, CSV or .xlsx) — Owner-only; preview is a pure dry-run, never
  writes; match by `code` when present → update, else insert

### Tasks — retired
*(Retired 04.11.2026 — order-workflow-revamp WP-H, Q17/Q17b.)* `/tasks`,
`/orders/{id}/tasks` are no longer mounted. The underlying table stays
for now (dropped in a later, separate migration).

### Commercial documents
- POST /orders/{id}/invoices — draft prefilled from lines
- GET /invoices?status|q|limit|offset — the central "Фактури" workspace's list
  (limit/offset landed; q search still future); each row batch-enriched with
  order_number/customer_name/total, never one query per row · GET /invoices/{id}
  · PATCH /invoices/{id} — drafts only
- POST /invoices/{id}/issue — assigns gapless number (Owner or toggle, 02 §12)
- POST /invoices/{id}/annul — {reason}; POST /invoices/{id}/reissue — new draft copy
- GET /invoices/{id}/invoice.pdf
- POST /orders/{id}/payments · payments listed within order/invoice payloads

### Dashboard & search
- GET /dashboard — the four widget counts + previews (02 §15), one call
- GET /search?q= — grouped results (customers/orders/assets), normalized (ADR-010)

### Platform (Owner)
- GET /platform/health — DB, disk, last-backup-verified age, license, jobs queue age
- GET|PATCH /platform/settings — company requisites, terms, toggles
- POST /platform/backup-run · GET /platform/backups · POST /platform/restore
  (wizard steps; also available pre-login from installer entry per 05 §5)
- GET /platform/license · POST /platform/license/refresh
- POST /platform/support-package — assembles artifact (03 §4), returns download or
  uploads (opt-in)
- GET /platform/updates · POST /platform/updates/apply — pipeline per ADR-014
- POST /platform/sample-check — restore-verification status detail (05 §4)

## 3. Contract freeze rules

The frozen items (07 §change process) bind this surface: status changes only via
`/orders/{id}/status`; timeline is read-only; issued invoices immutable (409 on
mutation attempts); every list is company-scoped by session, never by client
parameter (C3). Additive changes (new optional fields/endpoints) are free; breaking
changes require an ADR amendment and a `/v2` decision — which, at this product's
scale, should essentially never happen.
