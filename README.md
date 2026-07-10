# ServiceFlow

Working name (internal). A browser-based Service Management Platform for Bulgarian
repair businesses (2–10 people): customers → assets → service orders → repair
workflow → invoices. **V1 = local Windows deployment; V2 = cloud SaaS on the same
core.** Guiding principle: simple on the surface, robust underneath — and pragmatic
everywhere: no enterprise patterns without a concrete ServiceFlow problem; built to
be maintained by a single developer.

## Status

All documentation (00–13 + ADRs) is **PO-approved**. Implementation is in
**Stage 0** of [13_IMPLEMENTATION_PLAN.md](docs/13_IMPLEMENTATION_PLAN.md): repo +
module skeleton + CI are in place; the ADR-002 PostgreSQL hardening spike
([ops/spike](ops/spike/pg-hardening-checklist.md)) and the installer walking
skeleton ([ops/installer](ops/installer/README.md)) gate everything further —
no database schema may exist until the gate passes.

Layout: `backend/` (FastAPI modular monolith) · `frontend/` (React SPA) · `docs/`
(the frozen blueprint) · `ops/` (spike + installer) · see [CLAUDE.md](CLAUDE.md)
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
