# 13 — Implementation Plan

Status: **Approved by Product Owner 10.07.2026 — Stage 0 in progress** ·
Date: 10.07.2026 · Basis: everything frozen in 07
Planned for **one developer**. Durations are honest ranges, not commitments; each
stage ends runnable and demo-able. No stage starts before its gate.

## Stage 0 — Foundation & the ADR-002 gate (2–3 weeks)

Repo, module skeleton with import-boundary CI (ADR-001), dev environment (Docker
Compose: app + PostgreSQL), CI pipeline (12 §4), logging/error scaffolding, signed
build proof.
**The gate:** bundled-PostgreSQL hardening spike on reference VMs — silent install,
hard power-off survival, unattended minor upgrade, restore drill. **Pass → Alembic
migration #1 may exist. Fail → execute SQLite ramp (ADR-002) before any schema.**
Also here: installer walking skeleton (services + tray showing real health).

## Stage 1 — Identity & platform spine (2–3 weeks)

Companies/users/sessions schema · login, sessions, CSRF, PIN switch (ADR-008) ·
i18n scaffold with the bg catalog (ADR-015 CI check live from day one) · jobs runner
(ADR-006) · /platform/health · audit_log · settings.
*Acceptance:* two users on two LAN devices, PIN switching attributed in audit;
health honest about DB/disk.

## Stage 2 — Domain core (3–4 weeks)

Customers (normalization, duplicate warning, archive) · asset types + assets +
identifiers · orders with numbering, statuses, **full transition matrix + tests
(P0-1)** · timeline via domain events (ADR-011) · global search (ADR-010, P0-7).
*Acceptance:* order lifecycle end-to-end via API; timeline complete; search finds
Иван/Ivan/+359….

## Stage 3 — Order operations (3–4 weeks)

Diagnosis + approval rules · tasks (+call flag) · part lines with states · labor
lines · accessories · attachments (storage port, re-encode, thumbnails) · contact
records · derived money (P0-3).
*Acceptance:* the full order screen's data model works via API; E2E journey 1
passes headless.

## Stage 4 — The four screens (4–5 weeks)

App frame + intake flow (10 §3, the 2-minute target measured) · Kanban with DnD +
conflict handling · order detail · customer profile · dashboard · протокол print
(intake + delivery) · empty states + first-run checklist.
*Acceptance:* E2E journeys 1, 2, 4 pass in the browser; a non-developer completes
intake unassisted (hallway test).

## Stage 5 — Commercial documents (3–4 weeks, + accountant gate)

Invoices draft→issue→annul→reissue, gapless sequences (P0-2) · payments · VAT modes ·
invoice PDF · Фактури list · delivery dialog money integration.
**Gate: Bulgarian accountant reviews document templates, numbering, VAT handling and
the fiscal-receipt boundary before this stage is called done (Q2 decision).**
*Acceptance:* E2E journey 3; concurrent-issue test green.

## Stage 6 — Platform & vendor loop (5–6 weeks)

Backup artifact + nightly verify + restore wizard + bare-metal path (05; P0-4) ·
updater pipeline with rehearsal/rollback (04; P0-5) · license client with grace +
read-only mode (ADR-009) · support package · opt-in telemetry · **vendor cloud
minimal:** license API, signed update feed, support inbox, minimal admin console
(A4 scope).
*Acceptance:* 04 §6 and 05 §7 drills pass automated; a license expiry walkthrough
degrades to read-only and back.

## Stage 7 — Hardening & pilot (3–4 weeks + ~4 weeks pilot calendar)

Reference-VM matrix drills · security pass (11 checklist) · performance perception
budget (10 §9) · docs for the shop (one-page install, one-page daily use) · **pilot:
one real shop, ≥ 2 weeks of real work, weekly check-ins** · fix loop.
**Launch gates:** P0 list green · drills green · accountant sign-off · pilot shop
completes a week without developer help · legal texts reviewed.

## Sequencing logic & risk posture

Riskiest-first: the two things that could invalidate the plan (PostgreSQL
invisibility, installer viability) are Stage 0, before any domain code exists. The
accountant gate sits at Stage 5 where its findings are cheap to absorb. The vendor
cloud is late (Stage 6) because everything before it runs without licensing.
Total: **roughly 6–8 months** of focused solo work to pilot, plus pilot calendar.
If that number needs to shrink, the honest lever is scope (03-era V1.5 candidates),
never the gates.

## Out of scope for every stage

Anything in 00 §Roadmap V1.5+ · SaaS functionality beyond the C1–C8 constraints ·
configuration UIs for things seed data covers. The change process (07) guards this
plan; "it seemed easier while coding" is not a rationale.
