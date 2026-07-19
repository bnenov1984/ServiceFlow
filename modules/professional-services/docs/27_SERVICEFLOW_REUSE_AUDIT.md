# PS-27 — ServiceFlow Reuse Audit

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Audited against the real repository (branch `main`, commit `2f30cd1`):
`backend/src/serviceflow/*`, the frozen docs (00–15), the Business OS set
(BOS-00…16), and ADR-001…018 / ADR-BOS-001…004. This audit **builds on
BOS-02** (the platform's own classification) and takes its group A/B/C/D
verdicts as authoritative; the added value here is the per-capability
verdict *for this module*, in the commissioned six-way vocabulary:

- **R-CORE** — directly reusable shared Business OS capability (consume as-is)
- **R-PAT** — reusable architectural pattern (reimplement the shape, own the code)
- **R-ABS** — reusable only after abstraction (do not abstract now; build own or wait)
- **R-NO** — ServiceFlow-specific, not reusable
- **R-FUT** — potentially shared in the future (named trigger)
- **R-EVID** — unclear; requires implementation evidence

Governing platform rule (BOS-08 Phase 5, binding): where this module wants
something ServiceFlow *has*, it **builds its own or waits** — extraction
happens in Phase 6 from two concrete implementations.

## 1. Verdict table

| Capability (location inspected) | BOS-02 group | Verdict | Consequence for this module |
|---|---|---|---|
| Tenancy: Company, TenantContext, `scoped()`, RLS binding (`identity/`, `shared_kernel/db.py`) | A | **R-CORE** | consume via Core contracts; every `ps_*` table under the same RLS regime |
| Users, sessions, PIN switch, CSRF, owner gate (`identity/`, boundary per BOS-16) | A | **R-CORE** | consume `identity.deps` / `identity.contracts` only (lint-enforced boundary already exists) |
| Roles & permissions (single `is_owner`) | A (minimal) | **R-CORE + module extension** | keep Core boolean; module adds `ps_member_roles` ([20]) — the sanctioned "first module that needs finer grants pays" step |
| Technical audit log (`identity/models.py::AuditLog`) | A | **R-CORE** | platform security events stay there; module business history is separate ([30] §2) |
| UUIDv7 ids, naming conventions (`shared_kernel/ids.py`) | A | **R-CORE** | mandatory |
| Storage port (`shared_kernel/storage.py`, ADR-007) | A (port) | **R-CORE** | dossier bytes go through the port |
| Domain event bus (`shared_kernel/events.py`) | A (one fix pending) | **R-CORE** | note: `DomainEvent.order_id` leak — BOS-02 schedules the neutral-subject fix at "next natural touch"; **this module is that touch** ([35] Stage 0 flags it; we do not fix it unilaterally) |
| Text normalization (`shared_kernel/normalize.py`) | A | **R-CORE** | client search / dup hints |
| i18n mechanism: message keys, catalog pattern (ADR-015) | A (mechanism) | **R-CORE** | `ps.*` namespace; own catalog content |
| Health endpoint pattern (`platform/health.py`) | A | **R-CORE** | contribute module hook per BOS-06 |
| Registration, subscriptions, platform admin (Етап 3, not built) | A planned | **R-CORE (when built)** | module assumes tenant provisioning arrives platform-side; MVP pilots can be hand-provisioned like ServiceFlow dev tenants |
| Backup/export envelope (ADR-012, not yet SaaS-implemented) | A planned | **R-CORE (when built)** | module ships its export section (FR-PS-121) |
| Module activation/registry (BOS-06, not built) | A planned | **R-CORE (minimal form needed)** | this module + ServiceFlow coexisting makes `company_modules` real — Stage-0 platform work ([24] §6) |
| Customers (`customers/`: phone-first, translit shadow cols, GDPR flows) | C/D | **R-NO (entity) + R-PAT (two patterns)** | own `ps_clients` (ADR-PS-003); reuse *patterns*: normalization-backed dup hint, anonymization flow shape |
| Assets, asset types, identifiers (`assets/`) | C | **R-NO** | no physical asset exists in this domain — nothing to map |
| ServiceOrder aggregate + frozen status matrix + transition endpoint (`service_orders/`) | C | **R-NO (code) + R-PAT (two disciplines)** | reuse the *disciplines*: single transition chokepoint, server-owned state machine — applied to a different machine ([11]) |
| Diagnosis / approval gate | C | **R-NO** | no counterpart; professional engagements agreed up front ([03] §4) |
| Part/labor lines, accessories | C | **R-NO** | no counterpart |
| Protocol PDF (`service_orders/protocol.py`, fpdf2+DejaVu) | D | **R-FUT** | module has no MVP PDF; if a registry-extract print lands (F), compare with protocol+invoice plumbing then (BOS-02 already stages this for Етап 4) |
| Document numbering (`DocumentSequence`) | D / ownership Open | **R-PAT** | own `ps_number_sequences`; do NOT touch the shared table — its ownership is an open BOS-05 item between service_orders and commercial; joining that dispute adds a third claimant for zero gain |
| Tasks (`tasks/`, order-FK, `is_call`) | D | **R-NO (code) + R-PAT** | own `ps_tasks` with different semantics (kind, checklists); extraction candidate for Phase 6 comparison — R-FUT trigger recorded |
| Attachments pipeline (`attachments/`: re-encode, HEIC, thumbnails, order-anchored) | A(port)/D(module) | **R-ABS → build own minimal** | BOS-02 defers polymorphic-anchor generalization; module ships plain uploads ([17] §2); pipeline comparison is Phase-6 material |
| Contacts / ContactRecord (`contacts/`) | D | **R-NO (code) + R-PAT** | own `ps_communications` (richer types, direction); BOS-02's "revisit when CRM is real" stands — two implementations will exist then |
| Timeline (`timeline/`: append-only trigger, order-anchored, frozen catalog) | C (pattern documented) | **R-PAT** | own `ps_activity_events` with the same trigger discipline — exactly what BOS-02 §Activity history prescribes |
| Search (`search/` + normalization) | A(primitives)/C(impl) | **R-CORE (primitives) + R-PAT (module sources)** | module ships its own search sources; platform facade deferred |
| Dashboard read models (`dashboard/`) | D | **R-PAT** | own aggregate queries; no shared reporting framework |
| Notifications | D (nothing exists) | **build own** (ADR-PS-009) | first notification implementation on the platform; extraction comparison possible when a second module needs one — R-FUT |
| Invoicing/payments (commercial, Етап 4, empty package) | B candidate | **R-FUT via contract** | [21]: minimal module-local money now; consume commercial contract when it exists; never build invoice mechanics |
| Frontend shell, i18n plumbing, component library (`frontend/src/`) | platform | **R-CORE (shell/lib) + R-PAT (feature folders)** | module features live beside, never import, ServiceFlow features ([24] §4) |
| Local deployment infra (`ops/local-edition/`, parked by docs/14) | platform, parked | **R-EVID** | commissioned prompt assumed local-first; repo reality is web-first SaaS with local parked. Module stays local-*compatible* (no cloud-only dependency) but targets SaaS — assumption A-3 |
| Dev docker-compose, CI, import-linter, test harness | platform | **R-CORE (tooling)** | extend `.importlinter` + architecture tests with `ps` contracts in the first code PR |

## 2. Dangerous-reuse list (commissioned: where reuse would harm)

1. **Sharing `customers`** — couples two verticals on their most divergent
   entity and violates BOS data ownership; also poisons future extraction
   with premature union schemas. (Refused — ADR-PS-003.)
2. **Reusing the frozen status list/matrix** — ServiceFlow's statuses are
   repair vocabulary frozen by docs/02; configurable professional workflows
   need the two-axis model instead. Renaming their statuses would be the
   "superficial clone" the commission forbids. (Refused — ADR-PS-005.)
3. **Hanging module files on `attachments.order_id`** — schema violence.
   (Refused.)
4. **Extending `document_sequences`** with a third consumer while its
   ownership is an open dispute. (Refused.)
5. **Generalizing the event bus / timeline / tasks "while we're here"** —
   each is a BOS-02 group-D item with a named trigger that is *not* this
   module's MVP. (Refused; wants recorded in [24] §5.)
6. **Treating `serviceflow.platform` internals as importable Core** —
   forbidden by R2/BOS-04 regardless of convenience.

## 3. Net result

The module consumes **Core** (tenancy, identity, primitives, ports,
mechanisms, tooling) exactly as published, copies **five proven patterns**
(transition chokepoint, append-only trigger history, normalization-backed
dup detection, anonymization flow, typed-JSONB details), and **owns 100 %
of its domain code and tables**. Zero ServiceFlow domain code is imported,
modified, or extended. That is the intended Business OS outcome: the
platform is proven by a module that reuses everything platform-shaped and
nothing product-shaped.
