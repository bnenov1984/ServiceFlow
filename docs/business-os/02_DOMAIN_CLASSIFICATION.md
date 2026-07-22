# BOS-02 — Domain Classification

Status: **Phase 0 discovery — recommendations, not decisions** · Date: 17.07.2026
· Groups: **A** Business OS Core · **B** shared optional module · **C** ServiceFlow
domain · **D** unproven candidate (stays inside ServiceFlow until a second real
module proves reuse).

Confidence: High = evidence in code + docs today; Medium = behavior neutral but
anchoring is ServiceFlow-specific; Low = capability barely exists or not at all.

## 1. Classification table

| Capability | Group | Current implementation | Evidence of reuse | Confidence | Recommended action / timing |
|---|---|---|---|---|---|
| Organization/Company (tenant) | **A** | `identity/models.py::Company` + ADR-013 `company_id` everywhere | Every listed vertical needs a tenant; already the RLS axis | High | Isolate as Core identity; no code move before roadmap Phase 3 |
| Users, authentication, sessions, PIN switch | **A** | `identity/` (ADR-008; server-side sessions, CSRF, PIN) | Fully domain-neutral today; zero repair vocabulary | High | Same as above |
| Roles & permissions | **A (minimal)** | One `is_owner` boolean + `require_owner` (docs/08 §4 rejects role tables) | Real, but deliberately tiny | High | Keep boolean in Core. **Rejected:** building RBAC now — first module that needs finer grants pays for it |
| Audit log (technical) | **A** | `identity/models.py::AuditLog` | Security requirement of any tenant platform (docs/11 §2) | High | Core; keep separate from timeline (see 05 §3) |
| Numbering sequences | **D (unproven)** / **Open (table owner)** — *downgraded from A by review BOS-11 F3* | `service_orders/models.py::DocumentSequence` — generic shape (kind, year, current), used for order numbers; gapless invoice use comes in Етап 4 | One live consumer today (order numbers); invoices are future; other verticals hypothetical | Medium | Leave code in place; resolve table ownership in Етап 4 (conflict #2 in [01](01_REPOSITORY_ASSESSMENT.md#9-doc-vs-code-conflicts-found)); Core promotion only proposable with a second real numbered-document module |
| Localization mechanism | **A (mechanism only)** | message_key error contract (docs/09 §1, `main.py` handlers) + `frontend/src/i18n/bg.ts` (ADR-015) | Mechanism is product-agnostic; the catalog is ServiceFlow's | High | Mechanism → Core; formal per-module catalog namespacing **deferred to module #2** (Phase 5) — keys are already de-facto prefixed and renaming has no consumer (review BOS-11 F5) |
| Settings | **A (storage) / D (framework)** | `companies.settings` JSONB; no settings framework | One consumer; JSONB pattern is enough | Medium | Keep JSONB. **Rejected:** a settings registry/schema system now |
| Health / diagnostics | **A** | `platform/health.py` | Deployment requirement regardless of vertical | High | Core |
| Registration, subscriptions, billing, platform admin console | **A (planned)** | **Not built** — Етап 3, ADR-017/018 | Platform-level by definition (per company, not per vertical) | High (design) | Build in Етап 3 *as platform code, zero ServiceFlow imports* — cheapest Core proof available |
| Backup / restore / tenant export | **A (planned)** | Artifact format designed (ADR-012, docs/05/06); export not yet implemented in SaaS shape | Format is company-scoped, module-agnostic by design (C1–C8) | Medium | Етап 3 per plan; Core owns the envelope, modules own their sections — see [06_MODULE_CONTRACT.md](06_MODULE_CONTRACT.md) |
| Licensing / module activation | **A (planned)** | Subscription gating designed (ADR-018); per-module activation does not exist | Needed the day a second module exists | Medium | Design only now (ADR-BOS-004); implement with the second module |
| Storage port + attachments pipeline | **A (port) / D (module)** | Port: `shared_kernel/storage.py` (ADR-007). Pipeline: `attachments/` (re-encode, HEIC, thumbnails) hard-anchored to orders (`attachments.order_id` NOT NULL) | Port is neutral. Pipeline behavior is reusable but its anchor is ServiceFlow's | High (port) / Medium (module) | Port → Core. Attachments module stays in ServiceFlow; generalizing the anchor (polymorphic parent) is **Deferred** until module #2 needs files |
| Domain events bus | **A (with one fix)** | `shared_kernel/events.py` — neutral except `DomainEvent.order_id` | Timeline consumes it; search/notifications planned (ADR-011) | High | Core; **Recommended:** replace `order_id` with a neutral subject reference — but only at the next natural touch of the events code (second subscriber in Етап 3 or commercial in Етап 4), not as a standalone refactor (review BOS-11 F4); needs PO nod via the 07 process. **Naming:** published event *type names* are now a stable, module-namespaced contract (ADR-BOS-007) — ServiceFlow's existing unprefixed names are grandfathered, renamed at the same natural touch |
| Search | **A (primitives) / C (implementation)** | `shared_kernel/normalize.py` (pure, tested) + `search/` service reading ServiceFlow tables | Normalization: any Bulgarian-market vertical. Query service: knows customers/assets/orders specifically | High / High | Primitives → Core. Each module ships its own search sources; the cross-module facade's **ownership and shape are now fixed (ADR-BOS-006: Core-owned facade, modules only index via a `search` contract)**; the facade itself remains **Future candidate**, build still Deferred |
| Contacts (communication log) | **D** | `contacts/` — ContactRecord FK'd to customer + optional order | CRM/PropertyFlow would want *something* similar; only ServiceFlow proves it | Medium | Keep in ServiceFlow. Revisit when CRM is real |
| Customers | **C** (as modeled) / **D** (generic "Contact") | `customers/` — phone-first, translit shadow columns, GDPR anonymization, repair-shop shaped | Every vertical has "customers", but not *this* customer (see 05 §3 Customer vs Contact) | High (keep) | Stays ServiceFlow. **Rejected:** promoting to a shared Party/Contact model now |
| Addresses | — | Not modeled (customer address lives inside requisites JSONB where needed) | None | Low | Nothing to classify; do not invent |
| Tasks | **D** | `tasks/` — near-generic (title, assignee, due, done) but FK to service_orders and shop semantics (`is_call`) | ProjectFlow/SportFlow would need real task management — richer than this | Medium | Keep in ServiceFlow. A future ProjectFlow builds task management properly and *then* we compare |
| Comments & notes | **C** | "note" type on ContactRecord (deliberate: same mechanism, not a second entity) | — | High | Stays with contacts in ServiceFlow |
| Activity history (business timeline) | **C** | `timeline/` — append-only via DB trigger, order-anchored, event catalog from docs/01 §5 | The *pattern* recurs; the implementation is an order history | High | Stays ServiceFlow. Pattern documented for reuse; generic feed is **Deferred** |
| Notifications | **D (not built)** | Nothing (docs/08 §4: V1.5 outbox will add tables) | None yet | Low | Do not design in Phase 0 |
| Tags | **D (not built)** | Nothing | None | Low | Do not build |
| Custom fields | **Rejected as platform capability** | Typed JSONB + identifier extraction per module (docs/08 §4 explicitly rejects EAV) | — | High | Standing pattern stays; no EAV platform |
| Reporting foundations | **D** | `dashboard/router.py` — a few aggregate queries | One consumer, trivial | Low | Keep per-module read models; no reporting framework |
| Import/export foundations | **A (envelope, planned)** | ADR-012 versioned artifact (backup = GDPR export = migration), CI import harness planned (P0-8) | Format designed to be product-carrying | Medium | Core owns envelope + versioning; per-module sections when modules exist |
| Document generation (PDF) | **D** | `service_orders/protocol.py` — fpdf2 + DejaVu (Cyrillic), one document type | Invoices (Етап 4) will be consumer #2 — *then* extract a small pdf helper | Medium | Wait for Етап 4; extract only the font/layout plumbing that both actually share |
| Invoicing | **B (candidate)** | **Not built** (`commercial/` empty; schema designed docs/08 §commercial; BR-2/BR-3/gapless rules frozen) | ServiceFlow issues invoices; StockFlow/PropertyFlow plausibly would; **InvoiceFlow ingests supplier invoices — a different capability, not this one** | Medium | Build in Етап 4 **inside ServiceFlow's plan but as a cleanly-bounded module consuming order data via contract** — greenfield discipline is free there |
| Payments | **B (candidate, with invoicing)** | Not built (docs/08 §commercial `payments`) | Tied to invoicing above. Distinct from *subscription billing* (ADR-018, platform) | Medium | Same as invoicing |
| Inventory | **C-adjacent / future B** | Deliberately absent — `part_lines` are free-text, "no inventory, no reservations in V1" (model docstring, discovery S5) | StockFlow is the hypothetical prover | Low | Nothing to extract; StockFlow would be built as a module, ServiceFlow later *optionally* integrates via contract |
| Branches / locations | **D (not built)** | Nothing (single-location assumption throughout docs/00) | None | Low | Do not model |
| ServiceOrder aggregate, statuses, transition matrix, diagnosis, part/labor lines, accessories, protocol, warranty returns | **C** | `service_orders/` — frozen domain (docs/01/02) | This *is* ServiceFlow | High | Never leaves the module |
| Assets & asset types & identifiers | **C** | `assets/` | Repair-specific ("asset under repair") | High | Stays |

## 2. Reading of the table

- **Core (A) is already small and mostly already exists**: identity + tenancy +
  shared_kernel primitives + health, with Етап 3 adding the platform services
  (registration/billing/admin). No new Core code needs to be written for
  Business OS's sake — Етап 3 was going to build it anyway. The only Core
  *change* recommended is removing the `order_id` leak from the events bus.
- **Group B is currently empty in code.** The commercial module (Етап 4) is the
  first B candidate and the natural rehearsal for module discipline: it is
  greenfield, already has a reserved package, and its consumer relationship to
  service_orders (invoice from order lines) is exactly the cross-module contract
  pattern we want to prove.
- **Group D is the largest group by count, and that is the intended outcome** —
  tasks, contacts, attachments, timeline, document generation, reporting all
  *look* reusable and all stay put. Each has a named trigger (a second real
  module) rather than a date.

## 3. Extraction risk summary

| Capability | Extraction risk if done now | Main dependency knot |
|---|---|---|
| Identity/tenancy | Low (already isolated; everything depends on it downward) | none |
| Events bus | Low (one field rename ripples to timeline + publishers) | timeline subscriber |
| Attachments | High | `order_id` NOT NULL FK; stage vocabulary; RLS policy per table |
| Tasks | Medium | `order_id` FK, `is_call`, dashboard queries |
| Contacts | Medium | customer + order FKs, frozen BR (freeze window `frozen_after`) |
| Timeline | High | order FK, event catalog frozen in docs/01 §5, DB trigger |
| Numbering | Low-Medium | shared table with orders today; gapless invariant is P0-2 |
| Invoicing/payments | N/A (not built) | build-time discipline instead of extraction |
