# BOS-17 — Business Capabilities Matrix

Status: **Recommended — forward-looking registry, PO reviews on each
addition** · Date: 21.07.2026 · Source: PO review of docs/business-os +
modules/professional-services (this session)

## 1. Purpose

BOS-02 ([02_DOMAIN_CLASSIFICATION.md](02_DOMAIN_CLASSIFICATION.md)) answers
*"is capability X reusable, and who has it today"* — an audit of the real
ServiceFlow codebase. This document answers a different, forward-looking
question that grows more valuable as module count grows: **"which single
module owns capability X — today, on paper, or not yet at all"** — across
every module named anywhere in the Business OS vision (BOS-00 §2), whether
it has code, Phase-0 docs, or nothing.

It exists because the platform's own rule — every table, and now every
capability, has exactly one owner (BOS-05 §"every table has one owning
module") — needs a single place to check *before* a new module accidentally
claims a capability another module (or a future one already named in the
vision) was expected to own. It is the platform-level analogue of the
per-module traceability discipline Professional Services already committed
to (`modules/professional-services/docs/38_TRACEABILITY_MATRIX.md` §4).

## 2. Status vocabulary (this document only)

- **Existing** — real code owns it today.
- **Documented (Phase-0)** — a module's docs claim it; no code yet.
- **Future candidate — owner assigned** — Core is the designated eventual
  owner (by architectural necessity, e.g. tenancy), but it is unbuilt.
- **Future candidate — unassigned** — named only in the product vision
  (BOS-00 §2); no module has claimed it, no docs exist.

## 3. Matrix

| Capability | Owner | Status | Evidence |
|---|---|---|---|
| Identity, sessions, tenancy, RLS | Core | Existing | `identity/`, ADR-016 |
| Technical audit log | Core | Existing | `identity/models.py::AuditLog` |
| Storage port | Core | Existing | `shared_kernel/storage.py`, ADR-007 |
| Domain event bus (mechanism) | Core | Existing | `shared_kernel/events.py`, ADR-011 |
| i18n mechanism (message keys, catalog pattern) | Core | Existing | ADR-015 |
| Health endpoint | Core | Existing | `platform/health.py` |
| Registration, subscriptions, billing, admin console | Core | Documented (Етап 3) | ADR-017/018 |
| Backup / export envelope | Core | Documented | ADR-012 |
| Module registry / activation | Core | Future candidate — owner assigned | BOS-03 §2.6 |
| Global search facade | Core | Future candidate — owner assigned | ADR-BOS-006 |
| Customers & Assets (repair-shop) | ServiceFlow | Existing | `customers/`, `assets/` |
| Service Operations (orders, diagnosis, parts/labor, tasks, attachments, contacts, timeline, protocol PDF) | ServiceFlow | Existing | `service_orders/` + siblings |
| Order/invoice numbering (`document_sequences`) | ServiceFlow (`service_orders`) | Existing | ADR-BOS-005 |
| Invoicing, payments (commercial documents) | Commercial Documents | Existing (in progress, Етап 4) | `commercial/`, ADR-BOS-005 |
| Assignments, deadlines, next actions, workflow templates | Professional Services | Documented (Phase-0) | `modules/professional-services/docs/09`, `/13`, `/14`, `/12` |
| Clients (professional-services own — not shared with ServiceFlow Customers) | Professional Services | Documented (Phase-0) | ADR-PS-003 |
| Notifications (first real platform implementation) | Professional Services | Documented (Phase-0) | ADR-PS-009 |
| Tasks/checklists (professional-services own) | Professional Services | Documented (Phase-0) | `modules/professional-services/docs/15` |
| Document dossier (professional-services own) | Professional Services | Documented (Phase-0) | `modules/professional-services/docs/17` |
| Construction acts, technical passports, document generation, rules/templates | Construction Documentation | Documented (Phase-0) | `modules/construction-supervision/docs/11–19` |
| CRM / leads | — | Future candidate — unassigned | named only in BOS-00 §2 |
| Inventory / stock (StockFlow) | — | Future candidate — unassigned | named only in BOS-00 §2 |
| Property management (PropertyFlow) | — | Future candidate — unassigned | named only in BOS-00 §2 |
| General project management (ProjectFlow) | — | Future candidate — unassigned | named only in BOS-00 §2; **note:** if ever built, it is not "Professional Services renamed" — Professional Services deliberately excludes enterprise capacity planning (PS-02 §2.3); a real ProjectFlow would be its own module by the same anti-clone principle this whole package was built under |
| Booking/scheduling (SportFlow) | — | Future candidate — unassigned | named only in BOS-00 §2 |

## 4. Rules

1. **Exactly one owner per row.** A capability claimed by two modules'
   docs at once is a documentation bug, fixed immediately (same discipline
   as BOS-05's table-ownership matrix).
2. **A capability with no owner is a visible gap, never a silent
   assumption.** "—" in the Owner column means nobody has claimed it — it
   does not default to Core.
3. **A new module's Phase-0 commitment adds its rows here in the same PR**
   that creates its docs — mirrors the per-module traceability-matrix
   discipline (Professional Services PS-38 §4), generalized platform-wide.
4. **A capability's status is upgraded (Documented → Existing) only when
   real code lands** — this document never claims code that does not
   exist, per the platform's evidence-before-claim rule (BOS-00 §"do not
   claim a capability is reusable without inspecting it", inherited from
   the commissioning discipline of this session).

## 5. Maintenance

Updated whenever: a new vertical's Phase-0 docs are created; a capability's
status changes (Documented → Existing, or Future candidate gains an
owner); BOS-02's classification of an existing capability's group changes
in a way that affects ownership. Treated as a failing check in doc review
if stale, the same way a stale traceability matrix is treated within a
module (PS-38 §4).
