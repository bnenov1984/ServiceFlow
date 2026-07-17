# Diagram — Current Architecture (as implemented, commit `6c324ff`)

Everything on this page exists in code today. See
[01_REPOSITORY_ASSESSMENT.md](../01_REPOSITORY_ASSESSMENT.md) for the prose.

## Backend packages and real import direction

```mermaid
flowchart TB
    subgraph FE["frontend/ (React SPA — one app, feature folders)"]
        SHELL["shell · auth · dashboard · intake · orders · order · customers"]
        LIB["lib/api.ts · i18n/bg.ts · generated/ (openapi, transition matrix)"]
        SHELL --> LIB
    end

    LIB -- "HTTP /api/v1 (cookie session + CSRF, message_key errors)" --> MAIN

    subgraph BE["backend/src/serviceflow/ (one FastAPI app)"]
        MAIN["main.py + config.py + seed.py (composition root)"]

        subgraph DOMAIN["domain modules"]
            CUST[customers]
            AST[assets]
            SO["service_orders<br/>(orders, statuses, diagnosis, lines,<br/>accessories, protocol PDF, document_sequences)"]
            TSK[tasks]
            ATT[attachments]
            CON[contacts]
            TL["timeline (event subscriber)"]
            SRCH["search / dashboard (cross-module readers)"]
            COMM["commercial (EMPTY — reserved for Етап 4)"]
        end

        IDEN["identity<br/>(Company, User, Session, AuditLog,<br/>TenantContext construction)"]
        PLAT["platform (health only today)"]
        SK["shared_kernel<br/>(db base + RLS chokepoint · ids UUIDv7 ·<br/>events · storage port · normalize)"]
    end

    MAIN --> DOMAIN & IDEN & PLAT
    DOMAIN --> IDEN
    DOMAIN --> SK
    IDEN --> SK
    PLAT --> SK
    SO -- "domain events (in-proc, same tx)" --> TL
    SRCH -. "direct model reads (sanctioned, docs/03 §5)" .-> CUST & AST & SO & TSK

    PG[("PostgreSQL 16<br/>one schema · RLS FORCE on tenant tables<br/>non-superuser app role")]
    FS[("local filesystem storage<br/>(content-addressed, StoragePort)")]
    BE --> PG
    ATT --> FS
```

Enforced today (`backend/.importlinter`, CI): domain ↛ platform;
shared_kernel imports nothing above it. Not yet enforced: anything else.

## Request path (tenant scoping)

```mermaid
sequenceDiagram
    participant B as Browser (SPA)
    participant D as identity/deps.py
    participant S as module service
    participant DB as PostgreSQL (RLS)
    B->>D: request + sf_session cookie (+ X-CSRF-Token on mutations)
    D->>DB: resolve session → user
    D->>D: TenantContext(company_id, user_id, is_owner) — never from client input
    D->>DB: SET app.company_id (RLS GUC, rebound on re-begin)
    D->>S: handler(ctx, tenant-bound Session)
    S->>DB: scoped(select(...), Model, ctx) — the chokepoint
    S-->>S: publish(DomainEvent) → timeline writes in same tx
```

## Known coupling points (facts, listed in 01 §8)

- `shared_kernel.events.DomainEvent.order_id` — vertical concept in bottom layer
- `timeline_events.order_id` NOT NULL → timeline is order history
- tasks/attachments/contact_records FK → `service_orders.id`
- `document_sequences` defined in service_orders, filed under commercial in docs/08
- search/dashboard read other modules' models directly
