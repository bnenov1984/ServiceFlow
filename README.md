# ServiceFlow

Working name (internal). A **web-first, multi-tenant SaaS** Service Management
Platform for Bulgarian repair businesses (2–10 people): customers → assets →
service orders → repair workflow → invoices. A locally-deployed edition remains a
**parked future option** ([ops/local-edition](ops/local-edition/README.md)).
Guiding principle: simple on the surface, robust underneath — and pragmatic
everywhere: no enterprise patterns without a concrete ServiceFlow problem; built
to be maintained by a single developer.

## Status

All documentation (00–14 + ADRs) is **PO-approved**; the 11.07.2026 web-first
pivot is recorded in [14_WEB_FIRST_PIVOT.md](docs/14_WEB_FIRST_PIVOT.md).
Implementation follows [13_IMPLEMENTATION_PLAN.md](docs/13_IMPLEMENTATION_PLAN.md)
v3.0 — next up: **Етап 2, migration #1** (companies, users, sessions + tenant
isolation per ADR-016).

Layout: `backend/` (FastAPI modular monolith) · `frontend/` (React SPA) · `docs/`
(the frozen blueprint) · `ops/local-edition/` (parked) · see [CLAUDE.md](CLAUDE.md)
for working rules and commands.

## Documentation map (`docs/`)

| Phase | Documents |
|---|---|
| Discovery | [00 Product Discovery Report](docs/00_PRODUCT_DISCOVERY_REPORT.md) — incl. all PO decisions |
| Business | [01 Domain Model](docs/01_DOMAIN_MODEL.md) · [02 Business Workflow](docs/02_BUSINESS_WORKFLOW.md) |
| Architecture | [03 Architecture Discovery](docs/03_ARCHITECTURE_DISCOVERY.md) · [04 Update Strategy](docs/04_UPDATE_STRATEGY.md) · [05 Backup & Restore](docs/05_BACKUP_AND_RESTORE.md) · [06 Local→SaaS Migration](docs/06_LOCAL_TO_SAAS_MIGRATION.md) |
| Freeze | [07 ADR Index & Freeze](docs/07_ADR_INDEX.md) · [docs/adr/](docs/adr/) ADR-001…015 |
| Blueprint | [08 Database](docs/08_DATABASE_DESIGN.md) · [09 API](docs/09_API_SPECIFICATION.md) · [10 UI/UX](docs/10_UI_UX_SPECIFICATION.md) · [11 Security](docs/11_SECURITY_MODEL.md) · [12 Testing](docs/12_TESTING_STRATEGY.md) · [13 Implementation Plan](docs/13_IMPLEMENTATION_PLAN.md) |

## The non-negotiables (short form)

- Data is never hostage: read-only + export on license expiry (ADR-009).
- A backup that isn't proven restorable doesn't count (05).
- Updates can never destroy a shop (04).
- Issued invoices are immutable; corrections annul + reissue (ADR/01/02).
- The timeline is append-only and trustworthy (BR-5).
- UUIDs + company_id from row one; the backup artifact is the SaaS migration path
  (ADR-012/013, constraints C1–C8).
- Changes to frozen items go through the process in [07](docs/07_ADR_INDEX.md) —
  "seemed easier while coding" is not a rationale.
