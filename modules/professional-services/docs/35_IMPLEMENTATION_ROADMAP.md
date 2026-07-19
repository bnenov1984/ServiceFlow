# PS-35 — Implementation Roadmap

Status: **Draft for PO review — sequencing proposal, no dates** ·
Date: 18.07.2026 · Module: `professional-services`

Constraints: ServiceFlow's plan (docs/13) keeps priority; one developer;
every stage ends runnable; platform prerequisites are *coordinated with*,
never bundled into, module PRs. Model guidance follows the platform habit
(BOS-08): judgment-heavy stages — Fable 5; mechanical against approved
spec — Sonnet.

## Stage 0 — Platform prerequisites (not this module's code)

Coordinated platform PRs, each tiny, each its own review:

1. **BOS-08 Phase 3**: Core rename to `business_os.*` (trigger now met —
   [28] §3.1). Blocks Stage 1 (module code must never import
   `serviceflow.*`).
2. **Minimal activation**: `company_modules` + nav gating (BOS-06 minimal
   form).
3. **Event-bus neutral subject** (BOS-02's scheduled fix; the "natural
   touch" has arrived).

Exit: CI green, ServiceFlow behaviour unchanged, contracts R3/R5 hold in
the new package shape.

## Stage 1 — Skeleton + tenancy proof

Package skeleton per [10] §1; first migration: `ps_clients`,
`ps_client_contacts`, `ps_service_types`, `ps_member_roles`,
`ps_number_sequences` with full RLS; import-linter `ps` contracts + mapper
-ownership architecture test; **isolation tests for every table in the
same PR** (P0 discipline from day one). Minimal routers: clients CRUD,
service types CRUD. Exit: two seeded tenants provably isolated.

## Stage 2 — The aggregate

Migrations: `ps_workflow_templates` + stages, `ps_checklist_templates`,
`ps_assignments`, `ps_assignment_stages`, `ps_assignment_members`,
`ps_assignment_links`, `ps_activity_events` (+trigger). Lifecycle machine
(INV-4 chokepoint), numbering, copy-on-create semantics, typed-details
validation, starter seeds. Exit: J-1 backend complete (API-level test
green), T-1 suite green.

## Stage 3 — The engine (the product's heart; Fable-5 stage)

`ps_next_actions`, `ps_deadline_changes`, `ps_holiday_calendar`; pure
engine (risk + I-1…I-7) with T-2/T-3/T-4 complete **before** wiring; SQL
read models + property-test agreement; morning job + on-write recompute;
`ps_notifications` + dedup/digest/escalation (T-5). Exit: [13] §8 table
green, INV-9 demonstrated (recompute-from-export reproduces states).

## Stage 4 — The register around the engine

`ps_tasks`, `ps_document_requirements`, `ps_files` (storage port),
`ps_communications`, `ps_payment_entries` (+money shaping per role).
Deliver/complete/cancel flows, follow-up linking, anonymization flow.
Exit: J-4/J-5 API-level green; T-6/T-7 green.

## Stage 5 — Frontend MVP

Screens in value order: S-3/S-2 table (register usable) → S-1 dashboard +
S-10 notifications (control usable) → S-4 detail (dossier usable) →
S-5/S-6 clients → S-7/S-8/S-9 settings & workload → S-2a/S-2b tabs.
ps-feature boundary added to `architecture.test.ts`; T-9/T-11 as screens
land. Exit: J-1/J-2/J-3 end-to-end in the browser = **MVP exit gate
([37])**.

## Stage 6 — Pilot hardening

1–3 real firms (ideally one per reference service line); export section
wired into the platform harness when available; perf smoke at seeded
5 000; catalog copy review against [04]; pilot feedback triaged strictly
against [34] §2/§3 (the descope/defer lists are the shield against pilot
scope creep).

## Explicitly not scheduled

CS integration ([29] — needs both modules), commercial integration
([21] §3 — needs Етап 4), channels beyond in-app, everything F-class.
If ServiceFlow stage work collides, this module pauses — platform rule.
