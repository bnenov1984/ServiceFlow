# ADR-003 — Python + FastAPI Backend

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §D3

## Context
The backend must express a moderate CRUD+workflow domain quickly, validate rigorously
(money, statuses, legal documents), run as a Windows service locally, and be reused
unchanged in the SaaS edition. Team size is small; iteration speed on domain logic is
the scarcest resource.

## Decision
Python 3.12+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2. Distributed with a
bundled/embedded Python runtime owned by the installer (no system Python dependency).

## Alternatives considered
- **.NET 8 / C#** — the honest runner-up: best-in-class Windows service deployment
  (self-contained exe). Rejected because its decisive advantage is a one-time
  packaging problem we solve once in the installer, while Python's advantage
  (domain iteration speed, validation ergonomics) pays continuously.
- **Node.js/TypeScript** — single language across the stack, but weaker
  migration/ORM maturity for this domain shape and no packaging advantage. Rejected.

## Consequences
- **Advantages:** Pydantic models double as API contracts; Alembic discipline
  underpins the update strategy (04 §3); async runtime hosts the in-process job
  runner (ADR-006); large Bulgarian hiring pool.
- **Disadvantages:** Windows packaging is nontrivial (embedded runtime, signed
  binaries); Python performance ceilings — irrelevant at documented volumes.
- **Risks:** dependency sprawl. Mitigation: locked dependency set, minimal-deps rule
  in CODING_STANDARDS at blueprint stage.

## Reconsideration triggers
A future team that is decisively .NET-native before implementation starts; or
profiling at SaaS scale showing runtime limits (then: optimize or extract hot
modules, per ADR-001 triggers).
