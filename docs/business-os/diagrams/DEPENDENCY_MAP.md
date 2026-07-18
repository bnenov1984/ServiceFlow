# Diagram — Dependency Map (rules view)

Companion to [04_DEPENDENCY_RULES.md](../04_DEPENDENCY_RULES.md). Left: what CI
enforces today. Right: the target ratchet. Rule numbers R1–R10 are defined in 04.

## Enforced today (backend/.importlinter — Confirmed)

```mermaid
flowchart TB
    DOM["identity · customers · assets · service_orders ·<br/>commercial · timeline · attachments · contacts ·<br/>search · tasks"]
    PLAT["platform"]
    SK["shared_kernel"]

    DOM -- "allowed" --> SK
    PLAT -- "allowed" --> SK
    DOM -. "R1 FORBIDDEN ✗" .-> PLAT
    SK -. "R2 FORBIDDEN ✗ (anything above)" .-> DOM
```

## Target ratchet (Recommended; phase = when the rule becomes CI-enforced)

```mermaid
flowchart TB
    subgraph LEGEND[" "]
        direction LR
        A1[" "] -- "allowed" --> A2[" "]
        A3[" "] -. "forbidden ✗" .-> A4[" "]
    end

    V["ServiceFlow vertical<br/>(Customers & Assets + Service Operations)"]
    M2["Module #2 (future)"]
    CCON["commercial/contracts.py"]
    CINT["commercial internals<br/>(models · service · tables)"]
    SOCON["service_orders/contracts.py"]
    SOINT["service_orders internals"]
    CORE["Core: identity · platform"]
    SK2["shared_kernel (domain-neutral — R8)"]

    V -- "R4 (Phase 4)" --> CCON
    CCON --- CINT
    V -. "R4 ✗ internals" .-> CINT
    CINT -- "R4 (Phase 4)" --> SOCON
    SOCON --- SOINT
    CINT -. "R4/R5 ✗" .-> SOINT
    M2 -. "R5 ✗ any other module's tables" .-> CINT
    V -- "allowed" --> CORE
    CINT -- "allowed" --> CORE
    M2 -- "allowed" --> CORE
    CORE -. "R3 ✗ (Phase 1 — passes already)" .-> V
    CORE -. "R3 ✗" .-> CINT
    CORE -- "allowed" --> SK2
    V -- "allowed" --> SK2
```

## Rule → mechanism → phase summary

| Rule | Mechanism | Enforced from |
|---|---|---|
| R1 domain ↛ platform | import-linter (exists) | today |
| R2 shared_kernel bottom | import-linter (exists) | today |
| R3 Core ↛ modules | import-linter contract `core-not-modules` | **Phase 1 ✅ (18.07.2026)** |
| R4 contracts-only across context edges | import-linter, added with first `contracts.py` | Phase 4 (Етап 4) |
| R5 one writer per table | pytest over `Base.registry.mappers` (`backend/tests/test_architecture.py`) | **Phase 1 ✅ (18.07.2026, baseline)** |
| R6 free imports inside a context | scoping of R4/R5 (no rule needed) | — |
| R7 cross-context reads via query contracts | same as R4 | Phase 4 |
| R8 shared_kernel domain-neutral | review checklist (the one known violation is fixed at the next natural touch of events code — BOS-11 F4) | trigger-scheduled, not this phase |
| R9 frontend: leaf dirs ↛ feature folders (revised — see BOS-14) | `vitest` + `import.meta.glob` (`frontend/src/architecture.test.ts`) — no ESLint installed | **Phase 2 ✅ (18.07.2026)** |
| R10 cross-module transactions justified | review rule; ADR-011 timeline is the documented exemplar | today (convention) |
