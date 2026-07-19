# PS-08 — Non-Functional Requirements

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Numbered NFR-PS-nnn. Platform-inherited requirements are cited, not restated
in full (source in parentheses). Targets are sized for the pragmatism
directive: 1–15 users per tenant, tens-to-hundreds of active assignments.

## 1. Performance & capacity

| ID | Requirement |
|---|---|
| NFR-PS-01 | Dashboard and assignment list render < 1 s server time at 5 000 assignments/tenant; risk states computed by set-based SQL over indexed dates, not per-row app loops |
| NFR-PS-02 | Assignment detail (all panels) < 1 s; quick-entry actions (log communication, complete next action, tick task) < 300 ms perceived |
| NFR-PS-03 | Design ceiling 50 000 assignments and 100 000 files per tenant without schema change; no pagination-free endpoints |
| NFR-PS-04 | Notification generation job processes a tenant in < 5 s at design ceiling; runs per-tenant, isolated failures |

## 2. Correctness & determinism

| ID | Requirement |
|---|---|
| NFR-PS-05 | Risk, staleness, and notification outputs are pure functions of (stored data, org config, "today" in Europe/Sofia); same inputs ⇒ same outputs, unit-testable with a frozen clock ([13](13_DEADLINE_AND_REMINDER_ENGINE.md)) |
| NFR-PS-06 | All timestamps stored UTC (`timestamptz`); all date-only fields stored `date` and interpreted in Europe/Sofia; the boundary conversion exists in exactly one code location |
| NFR-PS-07 | Money `numeric(12,2)`; totals derived at read time (BR-3 discipline); currency default BGN, field present from day one (EUR transition reality in BG) |
| NFR-PS-08 | Sequence numbers unique per (org, year); gaps acceptable (no gapless requirement — unlike invoices) |

## 3. Security & isolation (30_SECURITY_PRIVACY_AND_AUDIT.md)

| ID | Requirement |
|---|---|
| NFR-PS-09 | ADR-016 in full: session-derived tenant context, scoped chokepoint, FORCE RLS + fail-closed GUC on every `ps_*` table, non-superuser app role; cross-tenant isolation tests are P0 and grow with every migration |
| NFR-PS-10 | Server-side permission enforcement for every route (module role matrix); UI hiding is convenience, not security |
| NFR-PS-11 | No PII in logs (docs/11 §3); file storage via storage port (ADR-007), keys unguessable, downloads authorised per request |
| NFR-PS-12 | Data minimisation: ЕГН/personal identifiers off by default; person-client anonymization supported without destroying assignment records |

## 4. Reliability & operations

| ID | Requirement |
|---|---|
| NFR-PS-13 | Tenant export includes all `ps_*` tables + file manifest (ADR-012 envelope); restore proves round-trip in CI once the platform harness (P0-8) exists |
| NFR-PS-14 | Background jobs (notifications, staleness) idempotent and safe to re-run; missed runs self-heal on next run (no "exactly once" assumptions) |
| NFR-PS-15 | Accidental-loss resistance: destructive UI actions confirm; business records soft-delete only ([26](26_BUSINESS_RULES.md) §deletion); forms preserve input on validation error |
| NFR-PS-16 | Single maintainer operability: no new infrastructure components beyond the platform's Postgres + app + existing job pattern (ADR-006) |

## 5. Usability & accessibility (22, 23)

| ID | Requirement |
|---|---|
| NFR-PS-17 | Bulgarian-first; all copy from `ps.*` catalog; no untranslated fallback visible (ADR-015 mechanism) |
| NFR-PS-18 | Usable without training: J-1 (intake) achievable by a first-day user in <60 s; every risk state has label + icon, never colour alone (WCAG 1.4.1) |
| NFR-PS-19 | Keyboard-operable core flows; visible focus; AA contrast; date inputs accept typed `дд.мм.гггг` |
| NFR-PS-20 | Narrow-screen (≥360 px) read-and-act support for dashboard, my-work list, assignment detail quick actions; complex configuration screens may be desktop-only |
| NFR-PS-21 | Works on ordinary office hardware / evergreen browsers; no native app, PWA stance inherited from ADR-004 |

## 6. Maintainability & evolution

| ID | Requirement |
|---|---|
| NFR-PS-22 | Module boundary lint-enforced (import-linter): `professional_services` imports Core contracts + shared_kernel only; no `serviceflow.*` domain imports ever (BOS-04) |
| NFR-PS-23 | Typed JSONB for per-service-type details with versioned shape documented in [25](25_DATA_MODEL.md); no EAV |
| NFR-PS-24 | English-ready i18n architecture: adding an `en` catalog requires no code change |
| NFR-PS-25 | All business rules in [26](26_BUSINESS_RULES.md) covered by unit tests before UI exists ([32](32_TESTING_STRATEGY.md)) |

## 7. Deployment posture

Web-first multi-tenant SaaS per the platform pivot (docs/14) — this module
adds no deployment machinery. The parked local edition remains compatible in
principle (nothing here requires cloud-only services: jobs are in-process
ADR-006 style, files go through the storage port). **Assumption recorded:**
MVP targets the SaaS deployment only; local-edition packaging of this module
is out of scope until the platform revives it ([36](36_RISKS_AND_OPEN_QUESTIONS.md) §A-3).
