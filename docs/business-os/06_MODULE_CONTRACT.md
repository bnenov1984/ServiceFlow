# BOS-06 — Module Contract (conceptual)

Status: **Phase 0 discovery — architectural contract only; nothing here is
executable, and no manifest file exists in the codebase** · Date: 17.07.2026 ·
Companion decision: [ADR-BOS-004](../adr/ADR-BOS-004-no-runtime-plugin-system-v1.md)
(no runtime plugins in v1).

## 1. Ground rules

- Modules are **built, tested, and deployed together** as one modular monolith
  (ADR-001/ADR-BOS-001). The manifest below describes *declared* properties,
  read at startup from code that is already linked in — never dynamically
  loaded, never third-party.
- "Activation" is data: a company has a set of active modules; inactive modules
  hide navigation, refuse their routes (404/403 with message_key), and skip
  seeding — their code still ships in the artifact.
- Until a second module exists, none of this is implemented. ServiceFlow does
  not need a manifest to be ServiceFlow. The contract exists now so that Етап-3
  platform work (navigation, permissions, export) is *shaped* to accept it
  later without rework.

## 2. Contract fields

| Field | Meaning | v1 semantics |
|---|---|---|
| `id` | stable module identifier | lowercase slug; doubles as table-name and i18n-key namespace prefix |
| `version` | module version | informational in v1 (everything ships together); becomes meaningful if release cadences ever split |
| `core_api` | Core contract version the module is built against | single number; checked at startup, mismatch = refuse to boot (not a solver — one version per artifact) |
| `requires` / `optional` | hard / optional dependencies on other modules' contracts | startup check: active module's `requires` must all be active for the same company; `optional` gates feature flags (e.g. ServiceFlow + commercial) |
| `migrations` | Alembic revisions owned by the module | single linear history per artifact (as today); each revision labeled with its owning module. Module-scoped branches: Deferred until proven necessary |
| `tables` | tables the module owns | feeds the R5 ownership test ([04](04_DEPENDENCY_RULES.md)) and the export manifest |
| `navigation` | nav entries contributed to the shell | replaces today's hardcoded shell nav when activation exists |
| `permissions` | permission keys the module introduces | v1 platform has only `owner`; field exists so a module *can* declare finer keys when RBAC is ever justified (see [02](02_DOMAIN_CLASSIFICATION.md) — Rejected for now) |
| `i18n` | catalog namespace(s) | e.g. all keys start `serviceflow.` — see roadmap Phase 2 namespacing |
| `settings` | settings keys stored under `companies.settings` (or module-owned table) | declared so the settings UI (Етап 3) can render per-module sections |
| `health` | health-check hook | contributes to `platform/health` endpoint |
| `export` | export/seed participation | module dumps/loads its own tables' section of the ADR-012 artifact; Core owns the envelope + format version |
| `events` | domain event types published / subscribed | documentation + collision guard; payloads are ids + primitives only; type names are module-namespaced and, once published, a stable contract (ADR-BOS-007) |
| `search` | searchable subject types contributed to the future global-search facade | module declares subject types + matched fields + a route template; Core owns the facade (query fan-out, ranking, permission filtering), never reads the module's tables directly (ADR-BOS-006). Declared now; the facade itself is Future candidate |

## 3. Non-binding example (YAML — illustrative, not a file format decision)

```yaml
# NOT IMPLEMENTED — conceptual illustration of the contract above.
id: serviceflow
version: 1.0.0
core_api: 1
requires: []            # identity/tenancy is Core, not a module — never listed
optional:
  - commercial          # invoicing; ServiceFlow degrades gracefully without it
tables:
  - customers
  - asset_types
  - assets
  - asset_identifiers
  - order_statuses
  - service_orders
  - diagnoses
  - part_lines
  - labor_lines
  - accessory_items
  - tasks
  - attachments
  - contact_records
  - timeline_events
  - document_sequences   # ownership Open — see BOS-05 §1
navigation:
  - key: nav.dashboard
    route: /
  - key: nav.orders
    route: /orders
  - key: nav.customers
    route: /customers
  - key: nav.intake
    route: /intake
permissions:
  - owner                # platform-provided; no module-specific keys in v1
i18n:
  namespace: serviceflow
settings:
  - warranty_default_days
  - protocol_terms_text
health:
  - orders_db_reachable
export:
  section: serviceflow
  format_version: 1      # inside the ADR-012 envelope
search:                  # declared per ADR-BOS-006; facade not built yet
  - subject_type: order
    fields: [number, customer_name]
    route: /orders/{id}
  - subject_type: customer
    fields: [name, phone]
    route: /customers/{id}
events:
  # Names below are the REAL implemented snake_case types (docs/01 §5 catalog;
  # do not invent a new naming convention — review BOS-11 F2). Excerpt:
  publishes: [part_added, labor_added, task_created, task_completed,
              task_reopened, attachment_added, attachment_deleted,
              note_or_contact_recorded]   # + order lifecycle events
  subscribes: [all]   # the timeline subscriber receives every published event
                      # (shared_kernel.events dispatches unfiltered)
```

## 4. Lifecycle (v1)

1. **Build:** module code is part of the monorepo; CI runs its tests always,
   active or not.
2. **Deploy:** one artifact, all modules included (ADR-017 CD pipeline).
3. **Migrate:** all modules' migrations run for every deployment; a company
   without the module active simply has empty module tables. (RLS makes them
   invisible anyway; empty tables cost nothing at this scale — pragmatism
   directive.)
4. **Activate:** platform admin (or plan entitlement, ADR-018) flips the flag →
   navigation appears, routes open, optional seed runs.
5. **Deactivate:** flag off → UI/routes gone; **data is retained**.
6. **Uninstall: does not exist in v1.** Limitations stated explicitly: no
   table drops, no data purge, no code removal per tenant. Getting data out =
   tenant export (ADR-012). A true uninstall story is Deferred until someone
   actually asks for it.

## 5. What this contract must not become

- A plugin SDK for third parties (ADR-BOS-004).
- A runtime code loader (`importlib` over entry points, etc.) — module list is
  a static, reviewed list in the composition root.
- A version-solver package manager — one artifact, one version set, always.
