# BOS-05 — Data Ownership

Status: **Phase 0 discovery — "current owner" columns are facts from code;
"proposed owner" columns are Recommended unless marked otherwise** ·
Date: 17.07.2026 · Table inventory from migrations 0001–0006 and
`backend/src/serviceflow/*/models.py`.

Conventions: public identifier is always the UUIDv7 `id` (ADR-013) — modules
never expose or accept another module's internal columns. "Readers" = code
allowed to SELECT; "Writers" = code allowed to INSERT/UPDATE/DELETE. All tenant
tables additionally carry `company_id` + RLS (ADR-016) — omitted below for
brevity.

## 1. Ownership matrix — existing tables

| Table | Current owner (package) | Proposed owner (context) | Allowed readers | Allowed writers | Migration concern | Status |
|---|---|---|---|---|---|---|
| `companies` | identity | Core: Identity & Tenancy | all modules (id + settings via contract) | Identity only | none | Recommended |
| `users` | identity | Core: Identity & Tenancy | all modules (id, name for attribution) | Identity only | none | Recommended |
| `sessions` | identity | Core: Identity & Tenancy | Identity only | Identity only | none | Recommended |
| `audit_log` | identity | Core: Identity & Tenancy | Identity (+ future platform admin console) | Identity only — `_audit()` is private to `identity/service.py` and no other module appends today; a Core append contract is future-if-ever-needed (review BOS-11 F6) | none | Recommended |
| `customers` | customers | SF: Customers & Assets | Customers & Assets; Service Ops (same vertical, R6); search/dashboard (same context) | customers service only | none | Recommended |
| `asset_types` | assets | SF: Customers & Assets | same as customers | assets service (seeded) | none | Recommended |
| `assets` | assets | SF: Customers & Assets | same as customers | assets service | none | Recommended |
| `asset_identifiers` | assets | SF: Customers & Assets | same + search | assets service | none | Recommended |
| `order_statuses` | service_orders | SF: Service Operations | all ServiceFlow packages; frontend via generated transition matrix | seed only (per-company rename comes in Етап 3) | global seed table — no company_id; stays inside the vertical | Recommended |
| `service_orders` | service_orders | SF: Service Operations | Service Ops packages; Commercial via **contract** (Етап 4) | service_orders service only (status only via transition endpoint — BR/CLAUDE.md rule 6) | none | Recommended |
| `diagnoses` | service_orders | SF: Service Operations | Service Ops; Commercial contract (estimate → invoice line source) | service_orders service | none | Recommended |
| `part_lines` | service_orders | SF: Service Operations | Service Ops; Commercial contract (billable lines) | service_orders service | none | Recommended |
| `labor_lines` | service_orders | SF: Service Operations | same as part_lines | service_orders service | none | Recommended |
| `accessory_items` | service_orders | SF: Service Operations | Service Ops | service_orders service | none | Recommended |
| `tasks` | tasks | SF: Service Operations | Service Ops (incl. dashboard) | tasks service | `order_id` FK is the coupling to undo *if* tasks ever generalize — not planned | Recommended (stays in SF) |
| `attachments` | attachments | SF: Service Operations | Service Ops | attachments service | `order_id` NOT NULL — generalizing means a polymorphic parent (Deferred) | Recommended (stays in SF) |
| `contact_records` | contacts | SF: Service Operations | Service Ops | contacts service | customer + order FKs | Recommended (stays in SF) |
| `timeline_events` | timeline | SF: Service Operations | Service Ops | timeline subscriber only; DB trigger forbids UPDATE/DELETE | order-anchored by design; see §3 Activity Feed vs Audit Log | Recommended (stays in SF) |
| `document_sequences` | service_orders (code) / commercial (docs/08) | **Open** — Service Ops keeps it, or Commercial takes it over in Етап 4, or it becomes a Core numbering service | orders service; invoices service (Етап 4) | owning service only (`SELECT … FOR UPDATE` — the single gaplessness point, P0-2) | two contexts will write one table in Етап 4 unless resolved; **first genuinely shared-write table** | **Open — decide in Етап 4 design, PO + dev** |
| `ps_clients` | professional_services.clients | Professional Services Operations (module #3) | Professional Services | clients service only | none — module-local, no shared FK from other modules | Implemented (walking skeleton, 18.07.2026) |
| `ps_assignments` | professional_services.assignments | Professional Services Operations | Professional Services | assignments service only (stage only via one transition function, same discipline as service_orders) | FK to `ps_clients.id`; `company_id` FK to `companies.id` | Implemented (walking skeleton, 18.07.2026) |
| `ps_next_actions` | professional_services.actions | Professional Services Operations | Professional Services | actions service only | FK to `ps_assignments.id`, `owner_user_id` FK to `users.id`; deadline risk computed at request time, not persisted | Implemented (walking skeleton, 18.07.2026) |

## 2. Ownership matrix — planned tables (not in any migration yet)

| Table (source) | Proposed owner | Readers | Writers | Status |
|---|---|---|---|---|
| `invoices`, `invoice_lines`, `payments` (docs/08 §commercial) | Commercial Documents | Commercial; Service Ops via contract (balance/status per order); platform export | Commercial only | Recommended |
| `jobs` (docs/08 §platform, ADR-006) | Core: Platform Services | Platform | Platform (modules enqueue via contract) | Recommended |
| subscription/billing state + webhook inbox (ADR-018) | Core: Platform Services | Platform; admin console | Platform | Confirmed (ADR-018) that it exists; ownership Recommended |
| export/`backup_runs`, `schema_meta` (docs/08 §platform, ADR-012) | Core: Platform Services | Platform | Platform | Recommended |
| `company_modules` (activation — ADR-BOS-004) | Core: Module Registry | Core + shell frontend | Platform admin flows | Deferred until module #2 |
| `license_state` (docs/08 §platform) | parked with local edition | — | — | Deferred (docs/14) |

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

**Invoice ownership.** Issued *sales* invoices belong to Commercial Documents
(Етап 4). Two look-alikes that must not be merged into it: (1) **InvoiceFlow**
as a product ingests and processes *incoming supplier* invoices — a document-
processing pipeline, not an issuing ledger; (2) **subscription billing**
(ADR-018) is the platform charging tenants — owned by Platform Services. Three
concepts, three owners. Status: Recommended.

**Payment ownership.** Customer payments against orders/invoices → Commercial
Documents (`payments`, docs/08). Tenant subscription payments → Platform
Services (provider-side, webhook-recorded). Status: Recommended.

**Inventory ownership.** Nothing to own — `part_lines` are deliberately
inventory-free free-text lines (model docstring; discovery S5; docs/08 §4 "no
multi-warehouse/inventory tables"). If StockFlow materializes it owns all
inventory tables, and ServiceFlow *optionally* consumes a stock contract from
it. Status: Confirmed (absent) + Deferred (StockFlow).

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
