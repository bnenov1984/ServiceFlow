# ADR-017 — Cloud Deployment & Continuous Delivery

Status: **Accepted** · Date: 11.07.2026 · Source: 14 (pivot) · Supersedes ADR-002
(bundled PG), ADR-005 (installer), ADR-014 (shop-side updates) for the primary
edition; those remain valid for the parked local edition.

## Context
Vendor-operated hosting replaces shop-operated Windows machines. Single developer;
EU market; small tenants; reliability and ease of deployment explicitly prioritized
by the PO over sophistication.

## Decision
- **One EU-region host** (Hetzner-class VPS or equivalent), Docker Compose–style
  deployment: app container (FastAPI + in-process jobs, ADR-006 unchanged),
  **managed PostgreSQL** (or same-host PG with automated backups + PITR until scale
  demands managed), Caddy/Traefik for TLS, S3-compatible object storage (ADR-007's
  port flips to its cloud adapter).
- **CD via GitHub Actions**: push to main → CI green → build image → deploy to
  staging → smoke (health + E2E subset) → manual approve → production. Migrations
  run expand–contract (kept from 04) and are **rehearsed against a staging copy of
  production data** before production applies (kept: rehearse-before-migrate).
- Environments: staging + production, config via environment, secrets in the host's
  secret store.
- No Kubernetes, no multi-region, no autoscaling until measured need (pragmatism
  directive).

## Alternatives considered
- **PaaS (Fly/Render/Railway-class)** — less ops, but EU data residency, pricing
  drift and platform lock-in for a product that must also ship a local edition
  someday; Docker-on-VPS keeps both editions on one artifact. Viable runner-up.
- **Kubernetes** — enterprise pattern with no concrete problem here. Rejected.
- **Serverless** — poor fit for in-process jobs + long-lived DB connections. Rejected.

## Consequences
Advantages: one deploy artifact for dev/staging/prod (and the future local
edition); minutes-to-production; the whole 04/05 shop-ops burden disappears from
V1. Disadvantages: we now run an internet-facing service — on-call reality,
hardening (11 rewrite), backups are our responsibility again (managed PG + tested
restores). Risks: single-host SPOF — accepted at launch, documented recovery
(restore to fresh host from backups, DNS flip; target < 2 h).

## Reconsideration triggers
Tenant count/load outgrowing one host; EU data-residency contracts requiring
specific providers; local-edition revival (re-activates parked ADRs).
