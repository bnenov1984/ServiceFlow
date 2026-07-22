# ADR-BOS-006 — Global Search is a Platform Capability; Modules Only Index

Status: **Accepted** (ownership & shape only — build stays Future candidate,
same discipline as Module Registry) · Date: 21.07.2026 · Source: PO review
of docs/business-os + modules/professional-services (this session)

## Context

BOS-02 already classifies search as split: normalization primitives
(`shared_kernel/normalize.py`) are Group A (Core); the query service
(`search/`) is Group C, ServiceFlow-specific, and a **cross-module search
facade is Deferred** with no shape decided.

That was fine with one vertical. It stops being fine once several exist:
ServiceFlow (existing), Professional Services and Construction
Documentation (Phase-0 docs), and the further verticals named in BOS-00's
vision (CRM, StockFlow, PropertyFlow, …). A user does not think in modules.
They type a client's name, an act number, a car model, or an order number
and expect one answer, not "which module do I open first." Left undecided,
each module in development risks either (a) building nothing and pushing
that burden onto the user, or (b) building its own cross-module search by
reaching into other modules' tables — a direct violation of BOS-04/05
ownership.

## Decision

1. **Global (cross-module) search is a Core / platform capability.** It is
   architecturally identical in status to Module Registry (BOS-03 §2.6):
   defined conceptually now, **not built** until its trigger fires. This
   ADR fixes *ownership and shape*, not a build date.
2. **Modules only index — they never aggregate.** A module that wants its
   records discoverable declares a `search` section in its module contract
   (BOS-06): a list of searchable subject types, each with the fields to
   match and a route template to open the result — e.g. Professional
   Services would declare `assignment` (number, title, client name) and
   `client` (name, phones).
3. **The future facade, when built, calls into each active module's own
   search implementation** (the module still queries its own tables, as
   `search/` does today) and merges/ranks/permission-filters the results.
   Core never queries another module's tables directly — no shared index
   table, no second source of truth.
4. **Module-local search is unaffected and stays module-owned.** Each
   module's own list/filter search (e.g. ServiceFlow's order search,
   Professional Services' assignment table search, FR-PS-080) continues
   exactly as designed — this ADR governs only the *cross-module* case.
5. **Modules being designed now must not build a bespoke global-search UI**
   that assumes reading beyond their own tables, and must not design their
   information architecture around "the user switches modules to search."

## Alternatives considered

- **(a) Leave it undecided per module** — rejected: exactly the failure
  mode this ADR exists to prevent; each module would guess differently.
- **(b) A shared search-index table every module writes into** — rejected:
  a second source of truth for data another module owns, the same
  anti-pattern BOS-00 §6 already rejects for custom fields (EAV).
- **(c) Facade owned by Core, calling into each module's own query logic
  via contract** — **chosen**: zero duplicated storage, respects
  ownership, degrades gracefully (an inactive module is simply not
  queried), and reuses the exact contract-call shape the platform already
  uses for `export`/`health` hooks.

## Consequences

- `06_MODULE_CONTRACT.md` gains a `search` field (declared, not built) —
  see companion edit.
- No code changes required today; no module is blocked or delayed.
- Professional Services and Construction Documentation design their own
  search sources now with this shape in mind, at zero present cost.
- The facade itself remains **Future candidate**: same trigger family as
  Module Registry — revisit when a second real module is in production
  and users are visibly switching modules to find things (BOS-08 roadmap
  Phase 5/6 spirit).

## Reconsideration triggers

A concrete user complaint about cross-module lookup once ≥2 verticals run
in production for a real tenant — build the facade then, against the
`search` contracts already declared.
