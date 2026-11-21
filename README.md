# ServiceFlow

**A web-first, multi-tenant SaaS platform for service businesses.**

ServiceFlow is an actively developed software product for small repair and service businesses. Its original vertical, **RepairFlow**, supports the customer-to-service-order workflow—from intake and asset tracking through diagnosis, tasks, repair, delivery, and commercial documents.

The guiding principle is **simple on the surface, robust underneath**: build maintainable software for small businesses without adding enterprise complexity unless it solves a concrete problem.

## Product

### RepairFlow — implemented

The core service-management vertical includes:

- Customer and asset management
- Service-order intake and lifecycle/status workflow
- Diagnosis and repair tasks
- Parts, labor, and accessory lines with derived totals
- Attachments, image processing, and thumbnails
- Contact records and notes
- Actor-attributed, append-only timeline
- Global search across customers, orders, and assets
- Delivery workflow and service history
- Warranty settings and employee administration
- Commercial-document workflows, including invoice draft, issue, annulment, and PDF generation

### Professional Services — implemented

A separate professional-services vertical is implemented within the platform.

### Construction Supervision — planned

This module is planned; backend implementation is not yet available.

## Architecture & Technology

- **Backend:** Python, FastAPI
- **Frontend:** React, TypeScript, Vite
- **Database:** PostgreSQL (Neon in deployed environment)
- **Deployment:** Render
- **Testing:** Pytest, Vitest, Playwright
- **Quality tooling:** Ruff, Mypy, import-linter
- **CI:** GitHub Actions

The repository is a modular monolith. BusinessOS platform capabilities—identity, tenancy, shared kernel, and platform administration—are separated from vertical applications such as RepairFlow and Professional Services.

## Engineering Highlights

- **Multi-tenant isolation:** Tenant context is derived from the authenticated session. Tenant-scoped queries pass through a scoped-query chokepoint, with PostgreSQL Row-Level Security as defense in depth.
- **Module boundaries:** Import contracts enforce separation between platform, shared kernel, and business modules.
- **Code quality:** Ruff and Mypy checks are part of backend verification.
- **Localization:** Bulgarian-first UI text is managed through localization catalogs.
- **Business data integrity:** Issued invoices are immutable; corrections use annulment and reissue. Timeline records are append-only.
- **Data portability:** Tenant export and read-only behavior after subscription expiry are product requirements.
- **Pragmatic architecture:** Designed for small service businesses and maintainability by a single developer.

Architecture decisions and product constraints are documented in the repository's ADRs and design documents.

## Testing

### Backend
- Pytest
- Ruff linting
- Mypy type checking
- Import-linter architecture contracts
- Tenant-isolation and cross-tenant access tests

### Frontend
- Vitest
- TypeScript type checking
- ESLint, including layer-boundary rules

### End-to-end
Playwright tests cover key journeys including authentication, RepairFlow order intake and delivery, status workflows, and parts of the invoice lifecycle.

**Latest documented verification (2026-09-20):**
- Backend: 750 tests collected (collection count; not a claim that all were executed in that review)
- Frontend: 506/506 Vitest cases passed across 50 files
- Ruff: clean
- Mypy: clean across 101 files
- Import-linter: 9/9 contracts kept, 0 broken
- Database-backed pytest execution was not repeated during that review; the last documented green CI run was on `main` at `cf6cb13`

See [the implementation plan](docs/13_IMPLEMENTATION_PLAN.md) for authoritative verification and current status.

## Live Deployment

The application is deployed on Render, with frontend and backend hosted separately and backed by Neon PostgreSQL.

- Frontend: https://serviceflow-frontend.onrender.com/

Availability and features may change during active development.

## Repository Structure

```text
.
├── backend/             # FastAPI backend and modular business/platform code
├── frontend/            # React SPA
├── docs/                # Product documentation, architecture, ADRs, and status
├── ops/local-edition/   # Parked future local deployment option
├── docker-compose.dev.yml
└── CLAUDE.md            # Development rules and commands
```

## Development Setup

### Prerequisites
- Python version specified by backend project configuration
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm (version specified by frontend configuration)
- Docker, for local development PostgreSQL

### Backend

```bash
cd backend
uv sync --dev
uv run pytest
uv run ruff check .
uv run mypy
uv run lint-imports
uv run uvicorn serviceflow.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
npm run build
```

Additional frontend checks and test commands are defined in `frontend/package.json`.

### Development Database

```bash
docker compose -f docker-compose.dev.yml up -d
```

This configuration is for local development. The deployed application uses managed PostgreSQL.

## Documentation

- [Documentation index](docs/INDEX.md) — document map and status
- [Implementation plan and current status](docs/13_IMPLEMENTATION_PLAN.md) — authoritative repo-wide status
- [Web-first SaaS pivot](docs/14_WEB_FIRST_PIVOT.md) — product/deployment direction
- [ADR index](docs/07_ADR_INDEX.md) — architectural decisions and change process
- [BusinessOS vision and scope](docs/business-os/00_VISION_AND_SCOPE.md)
- [Professional Services module](modules/professional-services/README.md)

## Current Status

The platform is actively developed. The current documented stage is SaaS Shell & Administration / Commercial Documents, with hardening and broader end-to-end coverage as the next major work.

Some release gates and planned features remain open. Subscription billing is currently vendor-admin-driven rather than fully automated through a billing provider, and accountant sign-off remains a documented gate for commercial-document release.

For current status, consult [the implementation plan](docs/13_IMPLEMENTATION_PLAN.md). This portfolio overview may not reflect every day-to-day change.

## Project Goals

ServiceFlow demonstrates practical work in:

- Full-stack product development
- Multi-tenant SaaS architecture
- Modular monolith design
- Tenant isolation and security
- API and frontend integration
- Automated testing at unit, integration, and end-to-end levels
- CI/CD and deployment
- Domain-driven business workflows
- Maintainable engineering practices
