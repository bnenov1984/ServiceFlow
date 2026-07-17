# BOS-10 — Glossary

Status: **Phase 0 discovery** · Date: 17.07.2026 · Terms are defined as used
across BOS-00…09 and reconciled with the frozen docs (01, 08, 14). Where a term
maps to a table or package, the mapping is given.

| Term | Definition | Repo mapping / notes |
|---|---|---|
| **Business OS** | The shared foundation (Core + shared modules + module contract) that future vertical products stand on. In v1: documented boundaries and lint rules inside this repo — not a separate deliverable. | docs/business-os/, ADR-BOS-001…004 |
| **Core** | The small platform layer every module needs: tenancy, identity/auth/sessions, technical audit, primitives (ids, db base, events, storage port, normalization), platform services (health; Етап 3: registration, billing, admin console, export). Admission test: ≥2 real modules need it *or* inherently platform-level, and zero vertical vocabulary. **Disambiguation (BOS-11 F7):** docs/01 §1 labels Service Operations "(core)" meaning ServiceFlow's core *domain* — the opposite end of the stack from BOS "Core". In BOS documents, capital-C Core always means the platform layer. | `identity/`, `platform/`, `shared_kernel/` |
| **Shared module** | An optional, reusable business capability above Core that modules may depend on but Core does not require. First candidate: Commercial Documents (Етап 4). None exist yet. | `commercial/` (reserved, empty) |
| **Vertical module** | A business product built on Core: ServiceFlow today; InvoiceFlow, StockFlow, etc. as future candidates. Owns its domain entirely. | `customers/`, `assets/`, `service_orders/` + satellites |
| **Module** | A package with identity, owned tables, own migrations/routes/i18n keys, and a declared contract surface; communicates with other modules only via contracts or events. | [06_MODULE_CONTRACT.md](06_MODULE_CONTRACT.md) |
| **Module activation** | A per-company data flag controlling whether a module's navigation/routes/seeds are available. Not code loading — all code ships in every artifact. | future `company_modules`; ADR-BOS-004 |
| **Modular monolith** | One deployable application with mechanically enforced internal module boundaries; no independently deployable parts. | ADR-001, ADR-BOS-001, `.importlinter` |
| **Bounded context** | A boundary within which a domain model is consistent and owned; contexts communicate via contracts. May span several code packages (Service Operations spans seven). | [03_BOUNDED_CONTEXTS.md](03_BOUNDED_CONTEXTS.md) |
| **Contract** | The deliberately public surface of a module: typed application functions (query/command) and event payloads. Excludes models, services, routers, tables. | future `<module>/contracts.py`; today de facto `identity/deps.py` |
| **Company** | The tenant: one paying business. Owner of all its data rows via `company_id` + RLS. In the parked local edition: exactly one per installation. | `companies` table (ADR-013/016) |
| **Organization** | *Not a ServiceFlow/Business OS concept.* No holding/franchise layer above Company exists or is planned. The term is banned in schemas to avoid Company/Organization drift. | Rejected — BOS-05 §3 |
| **Branch / location** | *Not modeled.* Single-location assumption stands (docs/00). Would be a future Company-owned entity if ever demanded. | absent by decision |
| **User** | A login identity within a company (email global-unique, password + optional PIN), carrying attribution (`created_by`, `performed_by`) and the `is_owner` flag. | `users` table |
| **Employee** | *Not a modeled concept.* No HR data exists. Any future HR capability would be a module-owned entity referencing `users.id`, not a rename of User. | BOS-05 §3 |
| **Customer** | ServiceFlow's counterparty: the person/firm whose asset is repaired. Phone-first, GDPR-anonymizable, may be a legal entity (`is_company` + requisites). Owned by ServiceFlow, not Core. | `customers` table |
| **Contact** | (a) `contact_records` — ServiceFlow's log of communications/notes on a customer/order; (b) hypothetical CRM "contact" — a different future concept, deliberately **not** unified with Customer. | BOS-05 §3 |
| **Service order** | ServiceFlow's central aggregate: one repair engagement for one asset, governed by the frozen status matrix, carrying diagnosis, lines, accessories, protocol, warranty linkage. | `service_orders` + aggregate tables (docs/01 §4) |
| **Work order** | Generic industry term. *Not a Business OS abstraction* — no generic WorkOrder entity will be created above ServiceOrder. | Rejected — BOS-05 §3 |
| **Timeline** | ServiceFlow's append-only, user-visible business history per order (DB-trigger-enforced). Distinct from the audit log. | `timeline_events`, ADR-011 |
| **Audit log** | Core's technical/security record: logins, PIN switches, admin actions. Never business history. | `audit_log`, docs/11 §2 |
| **Tenant context** | The server-derived triple (company_id, user_id, is_owner) that scopes every request; constructed only by the auth dependency. | `TenantContext`, `identity/deps.py::get_tenant` (ADR-016) |
| **Chokepoint** | `scoped()` — the single query-scoping function all tenant-table reads pass through. | `shared_kernel/db.py` |
| **Edition** | A deployment flavor of the same artifact: SaaS (primary) or local (parked). Module code is edition-blind. | docs/14, [07_DEPLOYMENT_MODEL.md](07_DEPLOYMENT_MODEL.md) |
| **Artifact (export)** | The ADR-012 versioned export: backup = GDPR export = inter-edition migration format. Core owns the envelope; modules own their sections. | ADR-012, docs/05/06 |
