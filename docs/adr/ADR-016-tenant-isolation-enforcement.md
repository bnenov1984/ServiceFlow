# ADR-016 — Tenant Isolation Enforcement (Web-First)

Status: **Accepted** · Date: 11.07.2026 · Source: 14 (pivot), promotes ADR-013 from
"carried" to "enforced"

## Context
As a public multi-tenant SaaS, cross-tenant data access is the single existential
security risk. Every table already carries `company_id` (ADR-013); the pivot makes
enforcement mandatory in V1.

## Decision
Three layers, cheapest-first:
1. **Server-derived tenant context** — company scope comes from the authenticated
   membership (session), never from client-supplied IDs. One dependency provides
   it; handlers cannot construct it any other way.
2. **Repository chokepoint** — all queries on tenant tables go through a scoped
   query layer that injects `company_id`; raw session queries on tenant tables are
   a review-blocker (DEVELOPMENT_RULES) and grep-able in CI.
3. **PostgreSQL RLS as defense-in-depth** — row-level security policies on tenant
   tables keyed to a per-request `SET LOCAL` tenant setting; catches the one query
   somebody forgets to scope. Enabled in production and in the test suite.

Mandatory isolation tests (P0 addition): company A cannot read/update company B's
customers, orders, attachments, search results; background jobs preserve scope.

**Deployment requirement (found during implementation):** the application must
connect as a **non-superuser role** — PostgreSQL superusers bypass RLS entirely,
silently disabling layer 3. The test suite mirrors this (migrates as admin, runs
the app as an unprivileged role) so a violation fails CI, not production.
Identity bootstrap tables (users/sessions/companies) are RLS-exempt with queries
centralized in `identity.service` as the compensating control.

## Alternatives considered
- **Schema-per-tenant / database-per-tenant** — stronger isolation, but operational
  cost (migrations × N, backups × N, connection pooling) is disproportionate for
  10–1000 small-shop tenants. Rejected; revisit only for a compliance-driven
  enterprise customer.
- **App-layer scoping only (no RLS)** — one forgotten filter = breach. RLS costs
  little here. Rejected.

## Consequences
Advantages: one schema, one migration chain, cheap ops, two independent safety
nets. Disadvantages: RLS adds session-variable plumbing and test-fixture care.
Risks: RLS policy drift vs schema — mitigated by a CI check that every tenant
table has a policy.

## Reconsideration triggers
An enterprise/compliance customer demanding physical isolation; measured RLS
overhead at scale (none expected at documented volumes).
