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
- GET /orders/{id} — full detail (lines, tasks, diagnosis, accessories, timeline page 1)
- PATCH /orders/{id} — fields per edit rules (row_version)
- POST /orders/{id}/status — {to, reason?, approval?} — the **only** way any client
  (incl. Kanban DnD) changes status; server enforces the matrix (02 §2)
- POST /orders/{id}/archive (terminal only) · POST /orders/{id}/warranty-return —
  creates linked order
- GET /orders/{id}/protocol.pdf — intake/delivery variants (?type=)
- CRUD nested, flat paths: /orders/{id}/diagnosis (PUT — single record),
  /orders/{id}/tasks, /part-lines, /labor-lines, /accessories, /contact-records
- PATCH /part-lines/{id} — incl. state changes (needed→ordered→received…)
- POST /orders/{id}/attachments (multipart) · GET /attachments/{id}/file — authorized
  stream (ADR-007), ?thumb= for photos · DELETE — soft
- GET /orders/{id}/timeline — paged, read-only

### Tasks (cross-order views)
- GET /tasks?today|mine|calls · PATCH /tasks/{id} (done, reassign, reopen)

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
- GET /dashboard — the six widget counts + previews (02 §15), one call
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
