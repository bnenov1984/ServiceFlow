# BOS-05 — Data Ownership

Status: **Phase 0 discovery — "current owner" columns are facts from code;
"proposed owner" columns are Recommended unless marked otherwise** ·
Date: 17.07.2026, §2 amended 26.07.2026 (Vendor Control Plane / RepairFlow
business profile planned tables — see
[18_VENDOR_TENANT_ADMINISTRATION.md](18_VENDOR_TENANT_ADMINISTRATION.md) §6),
§1 amended 27.07.2026 (the three Vendor Control Plane tables shipped in
migration 0012 and moved from §2 to §1), §1 amended again 28.07.2026 (the
RepairFlow `asset_types` company-scoping, migration 0015, also moved from
§2 to §1 — the last of the four §6 proposed changes to land) · Table
inventory from migrations 0001–0006 and
`backend/src/serviceflow/*/models.py`.

Conventions: public identifier is always the UUIDv7 `id` (ADR-013) — modules
never expose or accept another module's internal columns. "Readers" = code
allowed to SELECT; "Writers" = code allowed to INSERT/UPDATE/DELETE. All tenant
tables additionally carry `company_id` + RLS (ADR-016) — omitted below for
brevity.

## 1. Ownership matrix — existing tables

| Table | Current owner (package) | Proposed owner (context) | Allowed readers | Allowed writers | Migration concern | Status |
|---|---|---|---|---|---|---|
| `companies` | identity | Core: Identity & Tenancy | all modules (id + settings via contract) | Identity only — the Vendor Control Plane mutates rows too (`ProvisionCompany`, `grant_entitlement`/`revoke_entitlement`, docs/business-os/18 §11/§12) but only ever through `identity.contracts.provision_company`/`grant_module`/`revoke_module`/`set_business_profile`/`set_subscription_trial`, never a direct write; gained `subscription_state`/`subscription_state_changed_at`/`trial_ends_at`/`seat_limit` (migration 0014, ADR-BOS-012) | none | Implemented (subscription columns, 27.07.2026) |
| `users` | identity | Core: Identity & Tenancy | all modules (id, name for attribution) | Identity only — same as `companies`, the Vendor Control Plane's first-Owner creation goes through `identity.contracts.provision_company` only | none | Recommended |
| `sessions` | identity | Core: Identity & Tenancy | Identity only | Identity only | none | Recommended |
| `audit_log` | identity | Core: Identity & Tenancy | Identity (+ future platform admin console) | Identity only — `_audit()` is private to `identity/service.py` and no other module appends today; a Core append contract is future-if-ever-needed (review BOS-11 F6) | none | Recommended |
| `password_reset_tokens` | identity | Core: Identity & Tenancy | Identity only | Identity only | Tenant Forgot Password V1 — no `company_id` (looked up by `token_hash` alone, never listed per-tenant; the owning company is reachable via `user_id` -> `users.company_id`) | Implemented (Tenant Forgot Password V1) |
| `platform_admins` | platform_admin | Core: Vendor Control Plane | Vendor Control Plane only | Vendor Control Plane only; created out of band by the bootstrap CLI, never by an HTTP route | no `company_id` — RLS-exempt like `companies`/`users`; compensating control is centralized queries in `platform_admin/service.py` plus the `vendor-plane-private` import contract | Implemented (vendor security foundation, 27.07.2026) |
| `platform_admin_sessions` | platform_admin | Core: Vendor Control Plane | Vendor Control Plane only | Vendor Control Plane only | the distinct session kind ADR-BOS-009 requires — its own table, not a `kind` column on `sessions`, whose `company_id`/`user_id` are NOT NULL | Implemented (vendor security foundation, 27.07.2026) |
| `platform_audit_log` | platform_admin | Core: Vendor Control Plane | Vendor Control Plane only | Vendor Control Plane only, append-only (`platform_admin/audit.py::record` is the sole writer; a DB trigger forbids UPDATE/DELETE) | nullable `company_id` is a *target* reference, not a tenancy scope — no ORM-level FK (the vendor plane may not import `identity.models`), so the constraint lives in migration 0012 only | Implemented (vendor security foundation, 27.07.2026) |
| `customers` | customers | SF: Customers & Assets | Customers & Assets; Service Ops (same vertical, R6); search/dashboard (same context) | customers service only | none | Recommended |
| `asset_types` | assets | SF: Customers & Assets | same as customers | assets service only — seeded via `seed_default_types`, triggered by the `company_provisioned` domain event (never a direct call from identity/platform_admin, which may not import `serviceflow.assets` — ADR-BOS-011 §Decision 5) | **Company-scoped since migration 0015** (`company_id` + UUIDv7 `id`, RLS FORCE, unique `(company_id, code)`); `assets.asset_type_code` became `assets.asset_type_id` internally, wire contract unchanged. All five business profiles seed identical content today (docs/business-os/18 §15) — per-profile field_defs are future, additive work | Implemented (28.07.2026) |
| `assets` | assets | SF: Customers & Assets | same as customers | assets service | none | Recommended |
| `asset_identifiers` | assets | SF: Customers & Assets | same + search | assets service | none | Recommended |
| `order_statuses` | service_orders | SF: Service Operations | all ServiceFlow packages; frontend via generated transition matrix | seed only (per-company rename comes in Етап 3) | global seed table — no company_id; stays inside the vertical | Recommended |
| `service_orders` | service_orders | SF: Service Operations | Service Ops packages; Commercial via **contract** (Етап 4) | service_orders service only (status only via transition endpoint — BR/CLAUDE.md rule 6) | none | Recommended |
| `diagnoses` | service_orders | SF: Service Operations | Service Ops; Commercial contract (estimate → invoice line source) | service_orders service | none | Recommended |
| `part_lines` | service_orders | SF: Service Operations | Service Ops; Commercial contract (billable lines) | service_orders service | none | Recommended |
| `labor_lines` | service_orders | SF: Service Operations | same as part_lines | service_orders service | none | Recommended |
| `accessory_items` | service_orders | SF: Service Operations | Service Ops | service_orders service | none | Recommended |
| `catalog_items` | catalog | SF: Service Operations | Service Ops (`part_lines`/`labor_lines` creation reads it directly — same within-vertical sharing as `asset_types`, no contract needed); Commercial never reads it (invoice lines only ever see the snapshot already copied onto a line) | catalog service only, Owner-gated at the API layer (ADR-BOS-013) | `(company_id, code)` partial unique index WHERE code IS NOT NULL; items are archived, never deleted — `part_lines.catalog_item_id`/`labor_lines.catalog_item_id` must keep resolving | Implemented (order-workflow-revamp WP-I, 05.11.2026) |
| `order_adjustments` | service_orders | SF: Service Operations | Service Ops; Commercial via `service_orders.contracts.get_order_lines` (same path part/labor lines already use to prefill an invoice draft, source="adjustment") | service_orders service only, Owner-gated at the API layer, append-only (ADR-BOS-013) | `order_id` FK to `service_orders.id`; `created_by` FK to `users.id` | Implemented (order-workflow-revamp WP-I, 05.11.2026) |
| `tasks` | tasks | SF: Service Operations | Service Ops (incl. dashboard) | tasks service | `order_id` FK is the coupling to undo *if* tasks ever generalize — not planned | Recommended (stays in SF) |
| `attachments` | attachments | SF: Service Operations | Service Ops | attachments service | `order_id` NOT NULL — generalizing means a polymorphic parent (Deferred) | Recommended (stays in SF) |
| `contact_records` | contacts | SF: Service Operations | Service Ops | contacts service | customer + order FKs | Recommended (stays in SF) |
| `timeline_events` | timeline | SF: Service Operations | Service Ops | timeline subscriber only; DB trigger forbids UPDATE/DELETE | order-anchored by design; see §3 Activity Feed vs Audit Log | Recommended (stays in SF) |
| `document_sequences` | service_orders (code) / commercial (docs/08) | **Open** — Service Ops keeps it, or Commercial takes it over in Етап 4, or it becomes a Core numbering service | orders service; invoices service (Етап 4) | owning service only (`SELECT … FOR UPDATE` — the single gaplessness point, P0-2) | two contexts will write one table in Етап 4 unless resolved; **first genuinely shared-write table** | **Open — decide in Етап 4 design, PO + dev** |
| `ps_clients` | professional_services.clients | Professional Services Operations (module #3) | Professional Services | clients service only | none — module-local, no shared FK from other modules | Implemented (walking skeleton, 18.07.2026) |
| `ps_assignments` | professional_services.assignments | Professional Services Operations | Professional Services | assignments service only (stage only via one transition function, same discipline as service_orders) | FK to `ps_clients.id`; `company_id` FK to `companies.id` | Implemented (walking skeleton, 18.07.2026) |
| `ps_next_actions` | professional_services.actions | Professional Services Operations | Professional Services | actions service only | FK to `ps_assignments.id`, `owner_user_id` FK to `users.id`; deadline risk computed at request time, not persisted | Implemented (walking skeleton, 18.07.2026) |
| `ps_workflow_templates` | professional_services.catalog | Professional Services Operations | Professional Services | catalog service only | none — org-scoped reference data, no FK from other modules | Implemented (two-axis workflow slice, 23.07.2026) |
| `ps_workflow_template_stages` | professional_services.catalog | Professional Services Operations | Professional Services | catalog service only | FK to `ps_workflow_templates.id` | Implemented (two-axis workflow slice, 23.07.2026) |
| `ps_assignment_stages` | professional_services.assignments | Professional Services Operations | Professional Services | assignments service only (copy-on-create at assignment creation; never written from a template edit — ADR-PS-005) | FK to `ps_assignments.id`; `ps_assignments.current_stage_id`/`workflow_template_id` FK into this table and `ps_workflow_templates` respectively | Implemented (two-axis workflow slice, 23.07.2026) |
| `ps_assignment_stage_history` | professional_services.assignments | Professional Services Operations | Professional Services | assignments service only; DB trigger forbids UPDATE/DELETE (same discipline as `timeline_events`) | FK to `ps_assignments.id` and `ps_assignment_stages.id` (from/to); **not** routed through the shared domain-event bus — see BOS-09 Q8 (resolved) | Implemented (two-axis workflow slice, 23.07.2026) |
| `ps_deadline_changes` | professional_services.assignments | Professional Services Operations | Professional Services | assignments service only, via the reasoned-change chokepoint (`change_deadline`); DB trigger forbids UPDATE/DELETE | FK to `ps_assignments.id`, `changed_by` FK to `users.id`; mandatory `reason` (ADR-PS-008 §5) | Implemented (deadline engine slice, 23.07.2026) |
| `payments` | commercial | Commercial Documents | Commercial; Service Ops reads a derived paid_amount/balance summary via a `PaymentSummaryProvider` port it owns (service_orders/contracts.py) — commercial implements it, the composition root wires them; service_orders never imports commercial (architecture boundary repair, 20.07.2026) | commercial service only | `order_id` FK to `service_orders.id`; `invoice_id` FK to `invoices.id` (added by migration 0009, fulfilling migration 0008's promise) | Implemented (Payment recording, 19.07.2026) |
| `invoices` | commercial | Commercial Documents | Commercial; Service Ops via `service_orders.contracts.get_order_lines` (Invoice draft reads order part/labor lines this way, never `service_orders.models`/`.lines` directly) | commercial service only | `order_id` FK to `service_orders.id`; full docs/08 column set exists (number, seller/buyer, vat_mode, net/vat/gross, pdf_storage_key…) but this slice only ever writes `status="draft"` rows — everything else stays NULL until the issue slice | **Implemented — Draft only** (creation/list/detail/line-replace, 20.07.2026). Issue, numbering, annul/reissue, PDF, VAT remain not started. |
| `invoice_lines` | commercial | Commercial Documents | Commercial | commercial service only | `invoice_id` FK to `invoices.id` | **Implemented — Draft only**, 20.07.2026 |

## 2. Ownership matrix — planned tables (not in any migration yet)

| Table (source) | Proposed owner | Readers | Writers | Status |
|---|---|---|---|---|
| `jobs` (docs/08 §platform, ADR-006) | Core: Platform Services | Platform | Platform (modules enqueue via contract) | Recommended |
| subscription/billing state + webhook inbox (ADR-018) | Core: Platform Services | Platform; Vendor Control Plane | Platform | Confirmed (ADR-018) that it exists; V1 shape narrowed to manual state columns by ADR-BOS-012, ownership Recommended — see [18](18_VENDOR_TENANT_ADMINISTRATION.md) §6.3 |
| export/`backup_runs`, `schema_meta` (docs/08 §platform, ADR-012) | Core: Platform Services | Platform | Platform | Recommended |
| `company_modules`/`active_modules` (activation — ADR-BOS-004) | Core: Identity | all modules (read, via `is_module_active` contract) | **Vendor Control Plane only** once built (ADR-BOS-010); today CLI/seed only | **Implemented** as `companies.settings.active_modules` (JSONB), not a separate table — the "Deferred until module #2" note below is stale, module #2 (professional-services) shipped it 18.07.2026. Mutation path still needs the Vendor Control Plane — see [18](18_VENDOR_TENANT_ADMINISTRATION.md) §1.3 |
| `license_state` (docs/08 §platform) | parked with local edition | — | — | Deferred (docs/14) |
| ~~`platform_admins`, `platform_audit_log`~~ (Core, ADR-BOS-009) | Core: Vendor Control Plane | — | — | **Built 27.07.2026** (migration 0012, [18](18_VENDOR_TENANT_ADMINISTRATION.md) §9 phase 1) — moved to §1 above, together with `platform_admin_sessions`, which §6.2 did not enumerate but ADR-BOS-009's "distinct session kind" requires |
| ~~Company-scoped `asset_types`~~ (RepairFlow, ADR-BOS-011) | ServiceFlow: Customers & Assets (RepairFlow) | — | — | **Built 28.07.2026** (migration 0015, [18](18_VENDOR_TENANT_ADMINISTRATION.md) §15) — moved to §1 above, the largest of the four proposed §6 changes to actually land |

## 3. Ambiguous concepts — analyzed, not unified

**Customer vs Contact.** ServiceFlow's `customers` is a repair-shop counterparty:
phone-first, translit search columns, GDPR anonymization, `is_company` +
requisites for invoicing. A CRM "contact" (leads, pipeline, many-per-account) is
a different concept with different lifecycle. **Do not unify.** If a CRM module
ever exists, it owns its own contact tables and an explicit mapping
(customer ↔ contact link table) is designed then. *Similar name ≠ same concept.*
Status: Recommended (keep separate).

**Company vs Organization.** `companies` is the tenant — one row per paying
business (ADR-013/016). No "organization above companies" (holding/franchise)
requirement exists anywhere in docs/00–15. Introducing an Organization layer now
would be speculative. Status: Rejected (no Organization entity). Note the
naming wrinkle: `customers.is_company` means "counterparty is a legal entity" —
unrelated to the tenant table; glossary disambiguates ([10](10_GLOSSARY.md)).

**User vs Employee.** `users` are login identities with attribution semantics
(created_by, performed_by, PIN switching). There is no HR concept (contracts,
schedules, wages) anywhere in scope. A future SportFlow/ProjectFlow "team member"
is a user; if HR data ever appears it is a new module-owned entity referencing
`users.id`. Status: Recommended (User stays Core; no Employee entity).

**Service Order vs generic Work Order.** The ServiceOrder aggregate is welded to
repair semantics: frozen status matrix (docs/02), diagnosis with approval,
accessories, warranty returns (`origin_order_id`), protocol PDF, BR-2 reopen
rules. A generic WorkOrder abstraction would have to carry all of that as
"configuration" — precisely the workflow-engine anti-goal. PropertyFlow's
"transaction" or ProjectFlow's "project" share almost none of these invariants.
Status: Rejected (no generic Work Order).

**Invoice ownership.** Issued *sales* invoices belong to Commercial Documents.
Two look-alikes that must not be merged into it: (1) **InvoiceFlow** as a
product ingests and processes *incoming supplier* invoices — a document-
processing pipeline, not an issuing ledger; (2) **subscription billing**
(ADR-018) is the platform charging tenants — owned by Platform Services. Three
concepts, three owners. Status: Implemented — Draft only (20.07.2026); issue
(numbering, requisite snapshot, immutability), annul/reissue, PDF and VAT
remain Recommended/not started (Invoice decision checkpoint, docs/13 Етап 4).

**Payment ownership.** Customer payments against orders/invoices → Commercial
Documents (`payments`, docs/08). Tenant subscription payments → Platform
Services (provider-side, webhook-recorded). Status: Implemented (19.07.2026,
Payment recording — `invoice_id` nullable, no FK until Etap 4's `invoices`
table exists; a payment never requires an invoice, docs/01 §Payment).

**Inventory ownership.** Nothing to own — `part_lines` are deliberately
inventory-free (model docstring; discovery S5; docs/08 §4 "no
multi-warehouse/inventory tables"). *(Amended 05.11.2026 — order-workflow-
revamp WP-I, ADR-BOS-013):* lines are no longer free-text, but `catalog_items`
is a flat price list (name/code/unit/price), not inventory — no stock
levels, no quantities-on-hand, no suppliers; ADR-BOS-013 §7 names this limit
explicitly. If StockFlow materializes it owns all inventory tables, and
ServiceFlow *optionally* consumes a stock contract from it. Status:
Confirmed (absent) + Deferred (StockFlow).

**Task ownership.** `tasks` stay in Service Operations. They are shop-floor
checklist items (`is_call`, order-scoped, dashboard "my tasks"), not project
management. ProjectFlow/SportFlow-grade task management (hierarchies, deadlines,
workload) is a different capability that would be built in that module and
compared afterwards. Status: Recommended.

**Activity Feed vs Audit Log.** Already correctly split and documented:
`timeline_events` = business history of an order, append-only by DB trigger,
user-visible (BR-5); `audit_log` = technical/security record (logins, PIN
switches, admin actions), Core-owned (docs/11 §2; AuditLog docstring: "Business
history lives in the timeline, never here"). **Do not merge.** A future generic
per-entity activity feed is a Deferred pattern extraction, not a merge of these
two. Status: Confirmed (split exists) / Deferred (generic feed).

## 4. Tables currently touched by multiple packages

Facts from code, all within the Service Operations context (legal under R6):

- `service_orders`, `customers`, `assets`/`asset_identifiers` — read by
  `search/` and `dashboard/` directly.
- `service_orders` — read by tasks/attachments/contacts services for existence
  and status guards.
- `timeline_events` — written by the timeline subscriber inside publishers'
  transactions (ADR-011; the sanctioned cross-package transaction, R10 exemplar).
- `document_sequences` — written by service_orders today; invoices will need it
  in Етап 4 → the one **Open** ownership decision above.

No table is written by two contexts today. Keeping it that way is the point of
ADR-BOS-003.
