# Diagram — Target Modular Monolith (proposed, NOT implemented)

Everything on this page is **proposed future architecture** ([03](../03_BOUNDED_CONTEXTS.md),
[08](../08_EVOLUTION_ROADMAP.md)). It remains one deployable application at every
stage. Phase numbers refer to the roadmap.

```mermaid
flowchart TB
    subgraph ARTIFACT["One deployable artifact (always — ADR-001 / ADR-BOS-001)"]
        subgraph CORE["Business OS Core (Phase 3 gives it its own package name)"]
            SK2["technical primitives<br/>ids · db base + tenancy chokepoint ·<br/>events (neutral envelope, Phase 2) ·<br/>storage port · normalize"]
            IDEN2["Identity & Tenancy<br/>companies · users · sessions · audit_log"]
            PLATS["Platform Services (Етап 3)<br/>health · registration · subscriptions/billing ·<br/>admin console · export envelope (ADR-012) · jobs"]
            REG["Module Registry (Phase 5)<br/>company_modules activation"]
        end

        subgraph SFV["ServiceFlow vertical"]
            CA2["Customers & Assets"]
            SO2["Service Operations<br/>(orders + tasks + attachments + contacts +<br/>timeline + search + dashboard)"]
        end

        COMM2["Commercial Documents<br/>(shared-module candidate, built in Етап 4 / Phase 4)"]
        MOD2["Module #2 vertical<br/>(Phase 5 — InvoiceFlow / StockFlow / …)"]
    end

    SO2 -->|"same vertical: direct model reads allowed (R6)"| CA2
    SO2 <-->|"contracts.py only (R4):<br/>billable lines / buyer ⇄ invoice status / balance"| COMM2
    MOD2 -.->|"optional contract"| COMM2

    CA2 --> IDEN2
    SO2 --> IDEN2
    COMM2 --> IDEN2
    MOD2 --> IDEN2
    IDEN2 --> SK2
    PLATS --> IDEN2
    REG --> IDEN2
    SFV --> SK2
    COMM2 --> SK2
    MOD2 --> SK2

    PG2[("One PostgreSQL database<br/>every table has exactly one owning module (BOS-05)<br/>RLS per tenant unchanged")]
    ARTIFACT --> PG2

    style MOD2 stroke-dasharray: 5 5
    style REG stroke-dasharray: 5 5
    style COMM2 stroke-dasharray: 3 3
```

Key properties (all Recommended):

1. **Core never points up.** No arrow leaves CORE toward a module (rule R3 —
   lintable from Phase 1).
2. **Context edges are contract-only.** The single double-arrow
   (Service Operations ⇄ Commercial) is the first real one; module #2 gets the
   same treatment. Inside a vertical, packages stay informal (R6).
3. **Events flow through the neutral bus** in shared_kernel; payloads are ids +
   primitives; subscribers never import publisher models.
4. **Module Registry is data, not a loader** — dashed because it does not exist
   and is not built before module #2 (ADR-BOS-004).
5. **The database does not split.** Ownership is logical (matrix in BOS-05),
   enforced by lint/test — not by schemas, roles, or separate databases in v1.
