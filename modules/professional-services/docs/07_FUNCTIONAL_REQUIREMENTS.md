# PS-07 — Functional Requirements

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Numbered FR-PS-nnn; referenced by screens ([23](23_SCREEN_SPECIFICATIONS.md)),
acceptance criteria ([37](37_ACCEPTANCE_CRITERIA.md)) and the traceability
matrix ([38](38_TRACEABILITY_MATRIX.md)). Priority: **M** = MVP, **P** =
post-MVP, **F** = future (matching [34_MVP_DEFINITION.md](34_MVP_DEFINITION.md)).
Behavioural detail lives in the referenced model documents; this catalogue
states *what*, not *how*.

## 1. Clients (16_CLIENT_MODEL.md)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-001 | Create/edit clients of kind person or organisation; name mandatory, all else optional | M |
| FR-PS-002 | Client fields: phones, emails, address, EIK (org), notes, communication-preference note; personal identifier (ЕГН) **not stored** unless org enables the field per ADR-PS-003/GDPR | M |
| FR-PS-003 | Contact persons per client (name, role, phone, email) | M |
| FR-PS-004 | Client detail shows assignment history and money summary (agreed/paid/outstanding across assignments) | M |
| FR-PS-005 | Duplicate hint on create (normalized name/phone match) | P |
| FR-PS-006 | Client deactivation (hidden from pickers, history intact); no hard delete when assignments exist; GDPR anonymization for persons | M |
| FR-PS-007 | Typeahead client picker with inline minimal creation (name + phone) | M |

## 2. Service types & templates (12, 15)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-010 | CRUD service types: create, rename, deactivate, reorder | M |
| FR-PS-011 | Service type may reference a default workflow template and default checklist template | M |
| FR-PS-012 | Service type may define default document requirements list | M |
| FR-PS-013 | Service type extras: standard duration, default price, default assignee | P |
| FR-PS-014 | Deadline-calculation rules per service type (e.g. received + N working days) | F |
| FR-PS-015 | Starter set of service types + example workflows/checklists seeded on activation (org may delete) | M |

## 3. Assignments (09, 11)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-020 | Create assignment with: number (auto, per-org yearly sequence), title, client, optional client contact, service type, description, responsible owner, priority, received date; defaults from service type | M |
| FR-PS-021 | Dates per assignment, all distinct fields: received, planned start, internal target, official deadline (+ optional exact time), completion — never one generic field | M |
| FR-PS-022 | Team members list (participants besides the owner) | M |
| FR-PS-023 | Lifecycle states `active`/`delivered`/`completed`/`cancelled` with controlled transitions ([11](11_ASSIGNMENT_LIFECYCLE.md)); cancellation requires reason | M |
| FR-PS-024 | Stage position from the assignment's own workflow (copied from template at creation); one-click stage transition with validity rules | M |
| FR-PS-025 | Per-assignment typed details (JSONB) per service type: court/case/deposit for expertise; property data for valuation; project data for acts — no EAV | M |
| FR-PS-026 | Linked follow-up assignment creation from a terminal assignment, pre-filled, bidirectional link | M |
| FR-PS-027 | Delivery info on delivered state: date, method, recipient | M |
| FR-PS-028 | Archive filter (completed/cancelled hidden by default in lists) | M |
| FR-PS-029 | Editable org label for the Assignment object, applied across UI | M |

## 4. Next actions (14)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-030 | At most one open next action per assignment: description, owner, due date, optional reminder date, optional blocking reason, optional appointment flag, optional link to a task | M |
| FR-PS-031 | Completing/replacing a next action prompts for the successor; declining is explicit and recorded | M |
| FR-PS-032 | Dashboard/list surfacing of active assignments with no open next action | M |
| FR-PS-033 | Overdue next actions flagged and notified to the action owner | M |
| FR-PS-034 | Next-action history retained per assignment (append-only) | M |

## 5. Deadlines, risk, inactivity (13)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-040 | Deterministic risk state per assignment (`normal`…`breached`) from official deadline and org thresholds; internal target produces its own earlier warning stream | M |
| FR-PS-041 | Org-configurable thresholds (attention/urgent days); per-assignment override | M (override P) |
| FR-PS-042 | Official-deadline changes require a reason; full change history visible on the assignment | M |
| FR-PS-043 | Weekend/holiday display flag on deadlines (falls on non-working day); **no automatic date shifting** | M |
| FR-PS-044 | Inactivity signals per [13 §6]: stale, no-next-action, overdue-next-action, waiting-too-long, never-started, undelivered-closeout — all deterministic | M |
| FR-PS-045 | Working-day arithmetic for staleness thresholds using shipped BG holiday table | M |
| FR-PS-046 | Recurring reminders (e.g. weekly until done) | P |
| FR-PS-047 | Statutory term calculator (ГПК/АПК) | F |

## 6. Tasks & checklists (15)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-050 | Tasks per assignment: title, optional assignee, optional due date, done (with time+actor), kind task/checklist, manual order | M |
| FR-PS-051 | Checklist templates (org-level), instantiated on assignment creation via service type; ad-hoc instantiation too | M |
| FR-PS-052 | Progress indicator (done/total) on assignment cards and details | M |
| FR-PS-053 | Task dependencies, milestones as entities | F |

## 7. Documents & dossier (17)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-060 | Document requirements per assignment with states missing/requested/received/waived, dates, and link to the received file | M |
| FR-PS-061 | File upload to categorised dossier (10 fixed categories), download, delete-by-permission (soft), uploader+time recorded | M |
| FR-PS-062 | Image/PDF inline preview where browser-native | M |
| FR-PS-063 | Version metadata: re-upload creates a new version row, history visible | P |
| FR-PS-064 | OCR, auto-classification, AI naming/summary | F |

## 8. Communication log (18)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-070 | Quick-entry communication log: 9 types, direction in/out, occurred-at (defaults now), free note; ≤3 interactions for the common case | M |
| FR-PS-071 | Log entries visible chronologically merged into assignment activity view, and filterable alone | M |
| FR-PS-072 | Email/calendar/messaging ingestion | F |

## 9. Search, lists, views (22, 23)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-080 | Assignment table: filter by state, stage category, service type, owner, client, risk state, date ranges; sort; text search (number, title, client, description — normalized per shared_kernel) | M |
| FR-PS-081 | Saved default view per user ("my work") | P |
| FR-PS-082 | Kanban by stage for one workflow template at a time; drag = stage transition with same validity rules | M |
| FR-PS-083 | Deadline/calendar view (month/week) of official deadlines, internal targets, appointments | M |
| FR-PS-084 | Dashboard buckets per J-2 with counts and drill-down | M |
| FR-PS-085 | Team workload view: per user — active count, overdue, due ≤3/≤7 days, no-next-action, blocked | M |

## 10. Notifications (19)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-090 | In-app notifications for the 12 trigger types in [19 §2], with severity | M |
| FR-PS-091 | Deterministic dedup (one live notification per dedup key), acknowledge, snooze-until | M |
| FR-PS-092 | Org defaults + per-user per-type opt-out (cannot opt out of `breached` official deadlines) | M |
| FR-PS-093 | Escalation of breached official deadlines to manager+owner regardless of assignment owner | M |
| FR-PS-094 | Email/desktop channels | P |

## 11. Money (21)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-100 | Agreed price + currency on assignment; payment entries (advance/payment/expense/invoiced-record) with date, amount, note | M |
| FR-PS-101 | Derived totals: invoiced, paid, outstanding — always computed, never stored as editable fields | M |
| FR-PS-102 | Payment due date + overdue-payment signal (where price entered) | M |
| FR-PS-103 | Integration with commercial module invoicing via contract | P (blocked on Етап 4) |
| FR-PS-104 | Financial visibility restricted by role | M |

## 12. Team & administration (20)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-110 | Module roles per user: manager / worker / readonly (Core owner ⇒ full); assignment of roles by owner/manager | M |
| FR-PS-111 | Permission matrix per [20 §3] enforced server-side | M |
| FR-PS-112 | Org settings: assignment label, thresholds, holiday calendar year load, financial-visibility toggle | M |
| FR-PS-113 | Audit views: assignment activity (all users), deadline-change history (all who see the assignment), admin audit trail (owner) | M |

## 13. Platform obligations (28)

| ID | Requirement | Pri |
|---|---|---|
| FR-PS-120 | All data tenant-isolated per ADR-016 (RLS + scoped chokepoint); isolation tests P0 | M |
| FR-PS-121 | Module participates in tenant export/backup envelope (ADR-012) with its own section | M (rides Етап 3) |
| FR-PS-122 | All UI strings via `ps.*` bg catalog; backend errors as message keys | M |
| FR-PS-123 | Activity events published on the shared event bus for future cross-module consumers | P |
