# 08 — Database Design

Status: **Approved by Product Owner 10.07.2026** · Date: 10.07.2026 · Basis: 01, 02, ADR-002/010/012/013
Pragmatism directive applies: every structure below maps to an approved requirement.
Freezes at implementation start (first Alembic migration), after the ADR-002 Stage-0
gate passes.

## 1. Conventions (apply to every table unless stated)

- `id` UUIDv7 primary key · `company_id` FK (ADR-013) · `created_at`/`updated_at`
  timestamptz (UTC, C6) · `created_by` FK users where actions are attributable.
- Soft archival: `archived_at timestamptz NULL` (no boolean flags).
- Optimistic concurrency: `row_version int` on user-edited aggregates
  (service_orders, invoices-draft, customers, assets).
- Money: `numeric(10,2)` + `currency char(3)` on document-level records (Q3
  abstraction); V1 always `EUR`.
- Enums as text with CHECK constraints (cheap to extend, honest in dumps).
- No cross-module FKs that violate ADR-001 boundaries (timeline/search reference by
  id without cascading behavior).

## 2. Tables by module

### identity
- **companies** — name, requisites jsonb (ЕИК, ДДС №, МОЛ, address, IBAN, logo ref),
  vat_registered bool, settings jsonb (language, protocol terms text, warranty
  default days, backup destinations, testing_status_enabled, worker_can_issue_invoices).
  Exactly one row in V1; the schema doesn't know that.
  Implemented allow-listed `requisites` keys (docs/ACCOUNTANT_REVIEW.md §3
  R1/R2/R3/R4): `address`, `phone`, `eik` — no separate ДДС № field (always
  `"BG" + eik` once `vat_registered`), no МОЛ/IBAN/logo (R3/R4 LAW-CONFIRMED
  not required, logo out of scope). The full list above is the aspirational
  domain shape; this is the current implemented subset.
- **users** — name, email/login (unique per company), password_hash (argon2id, C5),
  pin_hash, is_owner bool, is_active bool, language.
  Two roles = one boolean (blueprint: Owner/Worker, one person may be both — Owner
  implies Worker abilities). A roles table is exactly the enterprise pattern we skip.
- **sessions** — user_id, device label, created/last_seen/expires, revoked_at.
- **audit_log** (technical, small) — user_id NULL, action (login, pin_switch,
  license_event, backup, restore, gdpr, settings_change, reveal_sensitive),
  detail jsonb, created_at. Business history lives in timeline_events, not here.

### customers
- **customers** — name, phone, phone2, email, is_company bool,
  **vat_registered bool NULL** (Customer VAT Identity prerequisite slice,
  migration 0019 — tri-state: NULL=unknown/unestablished, never backfilled
  or defaulted to false; False=confirmed not registered; True=confirmed
  registered), company_requisites jsonb NULL (B2B invoices), notes,
  **phone_normalized**, **name_translit** (ADR-010 shadow columns,
  trigram-indexed), anonymized_at NULL.
  Allow-listed `company_requisites` keys (docs/ACCOUNTANT_REVIEW.md §4 B1,
  the buyer/B2B-customer mirror of the companies row above): `address`,
  `eik`, `vat_number` — unlike the seller side's `"BG" + eik` derivation,
  the buyer's `vat_number` is a real stored field, always explicitly
  entered (never derived), required only when `vat_registered=True`.

### assets
- **asset_types** — code, name_bg, icon, field_defs jsonb: ordered
  `[{key, label_bg, type: text|number|date|choice, choices?, identifier?, sensitive?}]`.
  Seeded: phone, vehicle, laptop, other. No UI editor (S2) — new types ship as seed
  updates.
- **assets** — customer_id, asset_type_code, label (brand+model display),
  field_values jsonb, sensitive_values bytea NULL (encrypted passcode etc., 11 §5).
- **asset_identifiers** — asset_id, kind (imei|serial|vin|reg|other),
  value, **value_normalized** (unique-warn per company, trigram+btree indexed).
  Split from jsonb because search and duplicate-warning need real indexes (ADR-010).

### service_orders
- **order_statuses** — code PK, kind (working|waiting|ready|terminal_success|
  terminal_failure), sort, enabled bool, name_bg (renameable later; seeded per 02 §1).
  Transition matrix lives in code with tests — a DB rules table would be config
  theater for a fixed matrix.
- **service_orders** — number (per-company `YYYY-NNNNN`, unique), customer_id,
  asset_id, complaint text, status_code FK, technician_id NULL, priority
  (normal|high), promised_on date NULL, warranty_days int NULL, origin_order_id NULL
  (warranty returns), status_changed_at (Kanban "days in status"),
  delivered_at NULL, terminal_reason text NULL (required for Отказана/Анулирана per
  OQ-2), row_version.
  Totals and paid state are **always computed** from lines/payments (BR-3) — never
  columns.
- **diagnoses** — order_id unique (0..1 per 01), observed, cause, recommendation,
  estimated_cost, estimated_days, repairable bool, approval_required bool,
  approval jsonb NULL {approved bool, by_user, at, channel, amount}.
- **tasks** — order_id NULL (company-level allowed), title, is_done, assignee_id
  NULL, due_on NULL, note, is_call bool, completed_by/at.
- **part_lines** — order_id, catalog_item_id NULL (migration 0037,
  order-workflow-revamp WP-I — NULL on every line added before it, stays that
  way forever), name/code/unit_cost/unit_price (**snapshotted** from the
  catalog item at add-time, BR-3), qty, state (issued|ordered|installed —
  migration 0038, WP-J, Q15: a third value, "issued", widened onto Wave 2
  Issue 33's ordered|installed CHECK with no data backfill needed — the
  original 5-state needed|ordered|received|installed|removed was already
  folded into ordered|installed by migration 0022), has_warranty bool NOT
  NULL DEFAULT true (migration 0038, WP-J, Q14 — replaces the prior
  warranty_days int NULL column entirely; backfilled false only where the
  old value was exactly 0, true otherwise).
- **labor_lines** — order_id, catalog_item_id NULL (migration 0037, WP-I),
  description/code/unit/unit_price/unit_cost (snapshotted, BR-3), qty
  **numeric(10,2)** (migration 0037 — was integer; fractional for an hourly
  catalog item, ADR-BOS-013 §8), duration_min NULL, performed_by NULL.
- **accessory_items** — order_id, name, qty, returned bool.
- **order_adjustments** — order_id, amount numeric(10,2) (signed), reason,
  created_by, created_at (migration 0037, WP-I — resolves 01 OQ-5;
  append-only, no UPDATE/DELETE path in the service layer).

### catalog *(new module, order-workflow-revamp WP-I, ADR-BOS-013)*
- **catalog_items** — company_id, kind (part|labor), name, code NULL (unique
  per company when set), unit (pcs|hour), sale_price numeric(10,2),
  unit_cost numeric(10,2) NULL (Owner-only visibility, API layer), archived_at
  NULL (archived, never deleted — part_lines/labor_lines may still reference
  it). Migration 0037.

### contacts
- **contact_records** — customer_id, order_id NULL, type (call|email|message|visit),
  direction (in|out), summary, occurred_at, frozen_after (end-of-day edit rule, OQ-1).

### attachments
- **attachments** — order_id, storage_key (content hash, ADR-007), kind
  (photo|document), stage (reception|progress|completed|other), caption, mime, size,
  deleted_at NULL (soft, timeline-traced).

### commercial (Commercial Documents & Invoicing)
- **invoices** — order_id, status (draft|issued|annulled), number bigint NULL until
  issue (gapless per company at issue time via document_sequences row lock),
  issued_at, tax_event_date date NULL (migration 0018 — legally distinct from
  issued_at, ЗДДС чл. 114, ал. 1/docs/ACCOUNTANT_REVIEW.md §2; the one column added
  after the original frozen shape, since it wasn't part of it; NULL until a future
  Issue workflow populates it), seller jsonb + buyer jsonb (snapshots — self-contained
  documents), vat_mode (registered|not_registered), totals (net, vat, gross — stored
  at issue, frozen), currency, annuls_invoice_id NULL, annul_reason NULL,
  pdf_storage_key NULL.
- **invoice_lines** — invoice_id, description, qty **numeric(10,2)**
  (migration 0037, order-workflow-revamp WP-I — was integer; carries an
  hourly LaborLine's fractional hours through to the invoice), unit_price,
  vat_rate, source (labor|part|manual|adjustment), sort.
- **payments** — order_id, invoice_id NULL, amount, method (cash|card|bank),
  is_refund bool, note, received_by, received_at.
- **document_sequences** — company_id, kind (invoice|order), current bigint.
  `SELECT … FOR UPDATE` on issue; the single place gaplessness is enforced.

### timeline
- **timeline_events** — order_id, event_type (catalog from 01 §5), actor_user_id
  NULL (system), summary_data jsonb, created_at. Append-only: no UPDATE/DELETE
  grants for the app role. Index (order_id, created_at).

### platform
- **jobs** — type, payload jsonb, run_at, status (pending|running|done|failed),
  attempts, last_error, dedupe_key NULL unique. Powers ADR-006.
- **license_state** — single row: token, plan, expires_at, last_refresh_at, mode
  (active|grace|readonly).
- **backup_runs** — artifact path/key, size, started/finished, verify_status
  (pending|verified|failed), verify_detail jsonb, destination results jsonb.
- **schema_meta** — export format version, install id (anonymous, telemetry A3).

## 3. Indexes that matter (beyond PKs/FKs)

- customers: gin_trgm(name_translit), gin_trgm(phone_normalized)
- asset_identifiers: btree(value_normalized), gin_trgm(value_normalized)
- service_orders: (status_code) partial WHERE archived_at IS NULL; (promised_on)
  partial WHERE status not terminal; unique(company_id, number)
- invoices: unique(company_id, number) WHERE number IS NOT NULL
- tasks: (assignee_id, is_done), partial (is_call) WHERE NOT is_done
- timeline_events: (order_id, created_at)
- jobs: (status, run_at)

## 4. What is deliberately absent

No roles/permissions tables (one boolean) · no status transition table (code) · no
EAV field tables (typed jsonb + identifier extraction) · no stored totals on orders
(computed) · no multi-warehouse/inventory tables (V1.5 decision pending) · no
notification tables (V1.5 outbox will add them) · no tenant RLS locally (SaaS adds
enforcement; schema already carries company_id).

Open item for review: **OQ-DB1** — retention of `audit_log` (proposal: 24 months,
pruned by retention job). Everything else follows approved documents.
