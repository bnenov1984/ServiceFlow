# PS-25 — Data Model

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Persistence mapping of [09_DOMAIN_MODEL.md](09_DOMAIN_MODEL.md). Platform
invariants apply to **every** table: UUIDv7 `id` via `shared_kernel.ids.new_id`,
`company_id` NOT NULL, `created_at`/`updated_at` timestamptz, FORCE RLS
policy + fail-closed GUC (ADR-013/016). Prefix `ps_`. This is a design
document — **no migrations exist or may be created in this phase**.

## 1. Tables (22)

| Table | Key columns beyond platform-standard | Notes |
|---|---|---|
| `ps_clients` | kind, name, name_norm, phones jsonb, emails jsonb, address, eik, notes, communication_preference, personal_identifier (nullable, org-toggled [16] §4), is_active, is_anonymized | name_norm via shared_kernel normalization for search/dup-hint |
| `ps_client_contacts` | client_id FK, name, role, phone, email, is_active | |
| `ps_service_types` | name, is_active, sort, default_workflow_template_id FK?, default_checklist_template_id FK?, default_requirements jsonb (list of names), details_kind (enum: none/court_expertise/valuation/construction_acts/…) | details_kind selects the JSONB schema for assignments |
| `ps_workflow_templates` | name, is_active | |
| `ps_workflow_template_stages` | template_id FK, name, category (enum), sort | |
| `ps_checklist_templates` | name, is_active, items jsonb (ordered titles) | items as jsonb: template items have no behaviour — a child table adds joins for nothing |
| `ps_assignments` | number, title, description, client_id FK, client_contact_id FK?, service_type_id FK, owner_user_id?, priority (enum), lifecycle_state (enum), current_stage_id FK?, workflow_template_id FK? (provenance only), received_on, planned_start_on?, internal_target_on?, official_deadline_on?, official_deadline_time?, payment_due_on?, delivered_at?, delivery_method?, delivery_recipient?, completed_at?, completed_by?, cancelled_reason?, agreed_price numeric(12,2)?, currency (default BGN), details jsonb, details_kind, last_activity_at | unique (company_id, number); indexes §4 |
| `ps_assignment_stages` | assignment_id FK, name, category, sort | the instance copy ([12] §5) |
| `ps_assignment_members` | assignment_id FK, user_id, note | participants |
| `ps_next_actions` | assignment_id FK, description, owner_user_id, due_on, reminder_on?, blocking_reason?, is_appointment bool, task_id FK?, status (enum), done_at?, done_by? | **partial unique index (assignment_id) WHERE status='open'** — the ≤1-open invariant in the database |
| `ps_tasks` | assignment_id FK, title, kind (enum task/checklist), assignee_user_id?, due_on?, note?, sort, done_at?, done_by?, is_deleted | |
| `ps_document_requirements` | assignment_id FK, name, status (enum), requested_on?, received_on?, file_id FK?, note | |
| `ps_files` | assignment_id FK, category (enum), filename, storage_key, content_type, size_bytes, note?, uploaded_by, is_deleted, version_of FK? (P) | bytes via storage port |
| `ps_communications` | assignment_id FK, type (enum), direction (enum), occurred_at, note, client_contact_id FK?, created_by | |
| `ps_payment_entries` | assignment_id FK, kind (enum), amount numeric(12,2), on_date, note?, external_ref jsonb? (commercial-module link, P), created_by | totals derived, never stored |
| `ps_deadline_changes` | assignment_id FK, field (enum official/internal), old_value, new_value, reason?, changed_by | append-only (no UPDATE/DELETE grants) |
| `ps_activity_events` | assignment_id FK, type, payload jsonb (ids+primitives), actor_user_id?, occurred_at | append-only via same DB-trigger pattern ServiceFlow's timeline proved (pattern reuse, own table) |
| `ps_member_roles` | user_id, role (enum) | unique (company_id, user_id) |
| `ps_number_sequences` | year, current | unique (company_id, year); gaps acceptable (NFR-PS-08); **own table — document_sequences belongs to ServiceFlow/commercial (BOS-05 open item stays theirs)** |
| `ps_notifications` | recipient_user_id, type, severity, assignment_id FK?, message_key, params jsonb, dedup_key, acknowledged_at?, snoozed_until?, resolved_at?, delivered_channels jsonb | **unique (company_id, recipient_user_id, dedup_key) WHERE resolved_at IS NULL** |
| `ps_holiday_calendar` | year, dates jsonb, source (enum shipped/org_edited) | unique (company_id, year); seeded per year, org-editable |
| `ps_assignment_links` | assignment_id FK, relation (enum follow_up_of / cs_project), target_assignment_id FK? (intra-module links), target_module?, target_ref uuid? (opaque cross-module reference, [29]) | exactly one of target_assignment_id / (target_module, target_ref) set — check constraint |

## 2. Enum strategy

Lifecycle state, stage category, priority, task kind, requirement status,
file category, communication type/direction, payment kind, notification
type/severity, member role: **Python enums persisted as short strings**
(check constraints), not Postgres enums — additive evolution without
migration churn, matching platform practice.

## 3. JSONB shapes (typed, versioned — no EAV)

- `ps_assignments.details` validated against the schema selected by
  `details_kind`; draft schemas in [../schemas/assignments/](../schemas/assignments/)
  (court_expertise, valuation, construction_acts). Each shape carries
  `"v": 1`; app code owns migration-on-read for future versions.
- `phones`/`emails`: arrays of strings. `default_requirements`,
  `checklist items`, `dates`, `params`, `payload`: shapes documented beside
  their schemas. JSONB never holds money totals, deadlines, or anything
  the engine computes over (those are typed columns — [13] §1).

## 4. Indexes that matter (beyond PK/FK/uniques above)

- `ps_assignments`: (company_id, lifecycle_state), (company_id,
  official_deadline_on), (company_id, internal_target_on), (company_id,
  owner_user_id, lifecycle_state), (company_id, client_id), (company_id,
  last_activity_at), trigram/normalized index on title+number for search.
- `ps_next_actions`: (company_id, owner_user_id, due_on) WHERE
  status='open'.
- `ps_tasks`: (company_id, assignee_user_id, due_on) WHERE done_at IS NULL.
- `ps_notifications`: (company_id, recipient_user_id, acknowledged_at).
- `ps_activity_events`: (assignment_id, occurred_at).

All dashboard buckets and workload counts resolve against these — no
sequential scans at NFR-PS-01 volumes.

## 5. Integrity mechanics

- FKs are intra-module only + `user_id` references to Core users
  (cross-context FK to Core is platform-accepted practice — ServiceFlow
  does the same; never an FK to another module's tables).
- Append-only tables (`ps_deadline_changes`, `ps_activity_events`):
  INSERT-only for the app role, DB trigger blocks UPDATE/DELETE (timeline
  precedent).
- Soft deletes via `is_deleted` only where specified (tasks, files);
  assignments/clients never hard-delete with history ([11] §4, [16] C-4).
- Derived values (risk, staleness, money totals, missing-documents) exist
  only in queries/views — INV-9's mechanical face.

## 6. Retention & export

All `ps_*` tables + a file manifest participate in the tenant export
section per BOS-06/ADR-012 (FR-PS-121). No module-side retention deletion
policies in MVP ([17] §5); anonymization per [16] §4 is the only
data-removing operation.
