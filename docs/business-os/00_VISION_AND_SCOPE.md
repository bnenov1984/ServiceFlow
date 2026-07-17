# BOS-00 — Business OS: Vision and Scope

Status: **Phase 0 discovery document — for PO review, nothing here is frozen** ·
Date: 17.07.2026 · Author: architectural discovery pass over the ServiceFlow
repository as of commit `6c324ff`.

> Decision-status vocabulary used across all BOS documents:
> **Confirmed** (already decided in the frozen repo docs/ADRs) · **Recommended**
> (this discovery proposes it; needs PO approval) · **Open** (needs a decision,
> options listed) · **Deferred** (deliberately postponed until a stated trigger) ·
> **Rejected** (considered and declined, with reason).

## 1. Problem statement

ServiceFlow is a working product-in-progress: a multi-tenant web SaaS for small
Bulgarian repair shops (Етап 2 backend complete, frontend under way — see
[13_IMPLEMENTATION_PLAN.md](../13_IMPLEMENTATION_PLAN.md)). The product direction
is to build further business applications — InvoiceFlow, PropertyFlow, ProjectFlow,
StockFlow, SportFlow, a CRM — on the foundations ServiceFlow is proving.

The problem: without deliberate boundaries, the second product either (a) copies
ServiceFlow's platform code and diverges, or (b) reaches into ServiceFlow's
internals and welds the products together. Both outcomes are expensive to undo.
The risk today is small — the codebase is young and disciplined — but the cheapest
moment to draw the lines is now, on paper.

The equal-and-opposite problem: premature generalization. ServiceFlow was built
under a **pragmatism directive** (CLAUDE.md hard rule 1; 00 discovery): no
enterprise patterns without a concrete problem, sized for 2–10-person shops and a
single maintainer. Business OS must not violate the directive that made
ServiceFlow buildable.

## 2. Product vision

**Business OS** is the name for the shared foundation that future vertical
products stand on. It is not a framework, not a plugin host, and not a separate
deliverable in the near term. It is:

- a small **Core** (tenancy, identity, sessions, platform services) that every
  vertical needs and none may reimplement;
- a set of **shared modules** (e.g. commercial documents) that verticals may
  activate but Core does not require;
- **vertical modules** (ServiceFlow first) that own their business domain
  entirely;
- one **modular monolith** deployment carrying all of the above, with module
  availability controlled by activation, not by dynamic code loading.

ServiceFlow remains the first real product, ships on its current plan, and is
never blocked by Business OS work.

## 3. Relationship between Business OS and ServiceFlow

| Question | Answer | Status |
|---|---|---|
| Is Business OS a rewrite? | No. It is a re-labelling of boundaries that largely already exist (`shared_kernel`, `identity`, `platform` vs domain modules). | Recommended |
| Does ServiceFlow depend on Business OS? | Eventually yes — on its explicit contracts only. Today the dependency direction already holds mechanically ([backend/.importlinter](../../backend/.importlinter)). | Confirmed (direction) / Recommended (contracts) |
| Does Business OS depend on ServiceFlow? | Never. "Core compiles, tests, and boots with zero ServiceFlow modules present" is the **module-#2 / roadmap Phase 3+ exit criterion**, not a near-term obligation (review BOS-11 F8) — today everything deliberately lives in one `serviceflow` package. | Recommended |
| When does Core become "real" (own package)? | Not before a second real module is committed to. Until then Core exists as documented boundaries + lint rules inside the ServiceFlow codebase. | Recommended |

## 4. Definition: Core

Core is the set of capabilities that **almost every** vertical demonstrably needs
and that ServiceFlow has **already implemented in a domain-neutral way**:

- tenancy: company record, tenant context derivation, scoped-query chokepoint,
  RLS binding (ADR-016; `shared_kernel/db.py`);
- identity & access: users, sessions, PIN switching, CSRF, owner gate (ADR-008;
  `identity/`);
- technical audit log (`identity/models.py::AuditLog`);
- primitives: UUIDv7 ids, timestamps/naming conventions, storage port (ADR-007),
  in-process domain-event bus (ADR-011), text normalization;
- platform services: health, config, logging; later registration, subscriptions &
  billing (ADR-018, Етап 3), platform admin console;
- the i18n **mechanism** (message-key error contract, catalog pattern — ADR-015);
  catalogs themselves belong to modules.

Full capability-by-capability analysis: [02_DOMAIN_CLASSIFICATION.md](02_DOMAIN_CLASSIFICATION.md).

**Core must remain small.** The admission test is double: (1) at least two real
modules need it, or it is inherently platform-level (tenancy, auth); and (2) it
contains no vertical vocabulary. "Several hypothetical products might use it" is
explicitly not sufficient.

## 5. Definition: module

A module is a package with: an identity, owned tables (exclusive write access),
its own migrations, routers, i18n keys, and a declared contract surface. Modules
communicate only through contracts (typed application interfaces) or domain
events — never by importing another module's models, services, or by querying
another module's tables. The conceptual manifest is defined in
[06_MODULE_CONTRACT.md](06_MODULE_CONTRACT.md). In v1 all modules are built,
tested, and deployed together; "activation" is a data flag, not code loading
(ADR-BOS-004).

## 6. Non-goals (v1 of Business OS)

- No microservices, no independently deployable modules (reaffirms ADR-001).
- No runtime/third-party plugin system (ADR-BOS-004).
- No generic workflow engine — ServiceFlow's transition matrix is code, frozen
  (docs/02); a second workflow-shaped product must bring its own before any
  generalization is discussed.
- No event sourcing — the timeline is an append-only projection, not a source of
  truth (ADR-011).
- No custom-fields/EAV platform — docs/08 §4 deliberately rejects EAV; typed
  JSONB per module is the standing pattern.
- No marketplace, no third-party developers, no white-labelling.
- No new tenancy model — ADR-016 multi-tenancy is the platform model.

## 7. Anti-goals (over-engineering tripwires)

Any of these appearing in a PR is a review-blocker per the pragmatism directive:

1. An abstraction with exactly one consumer, justified by a future product.
2. A "generic" entity (WorkOrder, Party, Resource) replacing a concrete one
   (ServiceOrder, Customer) without a second product on the roadmap **in code**.
3. Core importing anything from a vertical module.
4. A registry/reflection/discovery mechanism where an explicit list works.
5. Configuration for behavior no real tenant has asked to vary.

## 8. Platform principles

1. **Extract only what is proven reusable. Isolate what is likely reusable. Keep
   speculative abstractions inside the first product.** (Governing rule of this
   whole effort.)
2. Modular monolith before any distribution (ADR-001, reaffirmed ADR-BOS-001).
3. Contracts over reach-ins: cross-module communication is explicit
   (ADR-BOS-003; [04_DEPENDENCY_RULES.md](04_DEPENDENCY_RULES.md)).
4. Every table has one owning module; ownership is written down
   ([05_DATA_OWNERSHIP.md](05_DATA_OWNERSHIP.md)).
5. Deployment stays out of the domain — the property that made the 11.07.2026
   pivot cheap (docs/14 §"Why the architecture absorbs this cheaply") is a
   platform invariant, not a lucky accident.
6. Boundaries are enforced by CI (import-linter), not by convention.

## 9. Success criteria

Business OS Phase 0 (this document set) succeeds if:

- the PO can review and accept/veto each Recommended decision individually;
- ServiceFlow's Етап 2–4 plan is unchanged and unblocked;
- the first enforcement step ([08_EVOLUTION_ROADMAP.md](08_EVOLUTION_ROADMAP.md)
  Phase 1) is reversible and behavior-preserving.

Business OS as a whole succeeds when a second real vertical module ships reusing
Core identity/tenancy/platform services **without modifying ServiceFlow's domain
modules** — that shipment, not this document, is the proof of the platform.
