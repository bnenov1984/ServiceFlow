# CLAUDE.md — ServiceFlow

**Web-first multi-tenant SaaS** service management platform for Bulgarian repair shops; a local edition is parked as a future option (11.07.2026 pivot, docs/14).
**Product/architecture decisions live in docs/** — see docs/INDEX.md, docs/07_ADR_INDEX.md, and docs/13_IMPLEMENTATION_PLAN.md. Business OS platform-core work has its own router at docs/business-os/CLAUDE.md.

## Hard rules (violations are review-blockers)

1. **Pragmatism directive (PO):** no enterprise patterns without a concrete ServiceFlow problem; sized for 2–10 person shops and a single maintainer.
2. **Tenant isolation (ADR-016):** tenant context derives from the session, never from client-supplied IDs; all tenant-table queries go through the scoped chokepoint; RLS policies on every tenant table (FORCE, fail-closed GUC); the app's DB role is never a superuser; isolation tests are P0.
3. Every table: UUIDv7 id (business_os.shared_kernel.ids.new_id) + company_id (ADR-013).
4. No user-facing literal strings in components — frontend/src/i18n/bg.ts keys only; backend returns message_key, never prose (ADR-015, 09 §1).
5. Module boundaries enforced by backend/.importlinter (ADR-001): domain modules never import business_os.platform; business_os.shared_kernel imports nothing above it.
6. Status changes only via the transition endpoint; issued invoices immutable; timeline append-only (BR-1…BR-10 in docs/01).
7. No PII in logs (11 §3). Money is numeric, totals always derived (BR-3).
8. P0 list in docs/12 §1 must stay green — regressions there block release.
9. **Agent development loop:** every logical work unit must end in a verified checkpoint and commit before the next work unit begins. See docs/agents/development-loop.md.
10. **Scope control:** do not silently absorb unrelated changes. By default, stop and re-scope at 10 changed files or 300 changed lines unless the larger diff is mechanical and explicitly part of the same acceptance criterion.
11. **Git:** commits are expected after passed checkpoints; pushes remain explicitly user-authorized.

## Commands

- Backend: uv sync --dev · uv run pytest · uv run ruff check . · uv run mypy · uv run lint-imports · uv run uvicorn serviceflow.main:app --reload
- Frontend: npm install · npm run dev · npm run build
- Dev DB: docker compose -f docker-compose.dev.yml up -d

## Language

Docs and code in English; UI and user-facing copy in Bulgarian (bg catalog). The PO communicates in Bulgarian — reply in kind.

## Agent skills

### Issue tracker

Issues and specs live as markdown files under .scratch/<feature>/. See docs/agents/issue-tracker.md.

### Triage labels

Canonical five-role vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See docs/agents/triage-labels.md.

### Domain docs

Single-context: CONTEXT.md + docs/adr/ at the repo root. See docs/agents/domain.md.

### Development loop

Use /checkpoint after each independently verifiable work unit. The complete operational rules are in docs/agents/development-loop.md.