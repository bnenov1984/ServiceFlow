# CLAUDE.md — ServiceFlow

**Web-first multi-tenant SaaS** service management platform for Bulgarian repair
shops; a local edition is parked as a future option (11.07.2026 pivot, docs/14).
**All product/architecture decisions live in `docs/` and are frozen** — read
[docs/07_ADR_INDEX.md](docs/07_ADR_INDEX.md) first; it lists what is frozen and
the change process. Current stage: see
[docs/13_IMPLEMENTATION_PLAN.md](docs/13_IMPLEMENTATION_PLAN.md) (status line at top).

## Hard rules (violations are review-blockers)

1. **Pragmatism directive (PO):** no enterprise patterns without a concrete
   ServiceFlow problem; sized for 2–10 person shops and a single maintainer.
2. **Tenant isolation (ADR-016):** tenant context derives from the session, never
   from client-supplied IDs; all tenant-table queries go through the scoped
   chokepoint; RLS policies on every tenant table (`FORCE`, fail-closed GUC);
   the app's DB role is **never a superuser** (superusers bypass RLS); isolation
   tests are P0.
3. Every table: UUIDv7 `id` (`shared_kernel.ids.new_id`) + `company_id` (ADR-013).
4. No user-facing literal strings in components — `frontend/src/i18n/bg.ts` keys
   only; backend returns `message_key`, never prose (ADR-015, 09 §1).
5. Module boundaries enforced by `backend/.importlinter` (ADR-001): domain modules
   never import `serviceflow.platform`; `shared_kernel` imports nothing above it.
6. Status changes only via the transition endpoint; issued invoices immutable;
   timeline append-only (BR-1…BR-10 in docs/01).
7. No PII in logs (11 §3). Money is `numeric`, totals always derived (BR-3).
8. P0 list in docs/12 §1 must stay green — regressions there block release.

## Commands

- Backend (in `backend/`): `uv sync --dev` · `uv run pytest` · `uv run ruff check .`
  · `uv run mypy` · `uv run lint-imports` · run dev:
  `uv run uvicorn serviceflow.main:app --reload`
- Frontend (in `frontend/`): `npm install` · `npm run dev` · `npm run build`
- Dev DB: `docker compose -f docker-compose.dev.yml up -d` (dev only — customers
  never get Docker, ADR-005)

## Language

Docs and code in English; UI and user-facing copy in Bulgarian (bg catalog). The PO
communicates in Bulgarian — reply in kind.
