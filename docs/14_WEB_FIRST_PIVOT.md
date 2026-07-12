# 14 — Pivot: Web-First SaaS (Local Becomes an Option)

Status: **PO decision 11.07.2026** · Amends the Etap-1 freeze via the 07 change
process (serious reason: fundamental deployment/business-model change).

## The decision

ServiceFlow launches as a **cloud-hosted, multi-tenant web SaaS**. The local
Windows edition is no longer V1 — it remains a **preserved future option** (the
work is parked, not deleted). Companies will register, subscribe and use the
product in the browser over the internet.

## Why the architecture absorbs this cheaply

The freeze deliberately kept deployment out of the domain:
- **C1–C8 constraints** (UUIDs, company_id everywhere, UTC, storage keys, portable
  credentials, versioned export format) were designed for exactly this move.
- Domain model (01), workflow (02), schema (08), API contracts (09), UI (10) are
  **unchanged** — multi-tenancy goes from "carried" to "enforced".
- The backend skeleton, module boundaries, i18n model, and all P0 tests survive.

## What is superseded / parked (see amended ADRs)

| Was | Becomes |
|---|---|
| ADR-002 bundled PostgreSQL + VM hardening gate | **Managed/cloud PostgreSQL (ADR-017). The VM gate is void — migration #1 is unblocked now.** Spike knowledge parked for the local edition. |
| ADR-005 native installer/services/tray | Parked (local edition option). |
| ADR-009 offline license tokens + 30-day grace | Superseded by **ADR-018**: subscription state gates access server-side; read-only + export-always degradation **kept** (product value, not a licensing artifact). |
| ADR-014 owner-triggered updates | Superseded by **ADR-017**: vendor-operated CD; expand–contract migration policy **kept**. |
| 04 update strategy (shop-side) | Standard CD pipeline (ADR-017); rehearsal-before-migrate principle kept against a staging copy. |
| 05 backup (shop-side artifact) | Managed DB backups + PITR; **the versioned artifact remains** as tenant export = GDPR export = local-edition migration path (ADR-012 intact, direction-agnostic). |
| 06 local→SaaS migration | Inverted: SaaS is home; 06's constraints C1–C8 stay binding; a future local edition imports the same artifact. |
| ops/spike + ops/installer | Moved to `ops/local-edition/` (validated, documented, dormant). |

## What enters V1 scope (was V2)

Registration & onboarding · email verification · subscriptions & billing ·
tenant-isolation enforcement (chokepoint + RLS defense-in-depth) · platform admin
console (companies/subscriptions overview + control) · internet-facing security
posture (11 rewrite) · cloud hosting & CD.

## Carried decisions (PO approved these for the SaaS concept on 10.07.2026 —
confirm or veto, defaults apply otherwise)

1. **Free trial without card** (14 days), card only at conversion.
2. **Automated monthly card billing** via provider adapter (Stripe-class, BG
   availability verified at implementation); webhook inbox, idempotent.
3. **Platform admin console** with full subscriptions overview + manual control.
4. Roles: Owner + Worker with progressive disclosure (solo companies see no role UI).
5. **Sample-data demo** («Зареди примерни данни») inside each trial company.
6. EUR, bg-BG, Europe/Sofia presentation — unchanged.

## What stays true regardless

Simple on the surface, robust underneath · the four screens · the transition
matrix · timeline with actor attribution · BR-1…BR-10 (incl. the amended BR-2) ·
pragmatism directive: no enterprise patterns without a concrete problem, single
developer maintainability.
