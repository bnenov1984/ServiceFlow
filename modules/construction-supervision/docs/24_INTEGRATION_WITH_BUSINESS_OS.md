# CS-24 — Integration with Business OS

Status: **Draft for PO review — this is the module's governing boundary
document.** Date: 18.07.2026 · Companions: BOS-00…10, ADR-BOS-001…004,
ADR-CS-001, ADR-CS-006.

## 1. Standing

Construction Supervision is **Business OS vertical module #2**, the "second
real module" BOS-08 Phase 5 anticipates. Its commitment triggers, in order:

1. **BOS Phase 3** (Core package rename to `business_os.*`) — precondition
   for module #2 code, so module #2 never imports `serviceflow.*` (BOS-08
   Phase 5 prerequisites). *This documentation package is the paper
   commitment; the PO confirms before any code.*
2. **BOS Phase 5** rules apply verbatim: where this module wants something
   ServiceFlow has, it **builds its own or waits**; extraction happens in
   Phase 6 from two concrete implementations.

Dependency direction: `construction_supervision` → Core contracts only.
Never → `serviceflow.*`, and Core never → `construction_supervision`
(import-linter contracts extended in the module's first code PR).

## 2. Component classification (as required by the task brief)

Categories: **[CORE]** Business OS Core responsibility · **[SHARED]** shared
platform capability (activatable, not Core-required) · **[MODULE]**
Construction Supervision responsibility · **[FUTURE-X]** future extraction
candidate (BOS Phase 6) · **[UNDECIDED]** pending implementation evidence.

| Component | Class | Rationale / boundary |
|---|---|---|
| Tenancy (company, tenant ctx, RLS chokepoint) | **[CORE]** | ADR-016 platform model; module adds tables + policies only |
| Identity, sessions, roles, CSRF, owner gate | **[CORE]** | consumed via `identity.deps`/`contracts` (BOS-16); module defines its role semantics on top |
| UUIDv7 ids, naming/timestamps conventions | **[CORE]** | `shared_kernel.ids` as-is |
| In-process domain event bus | **[CORE]** | ADR-011; module's events stay module-internal |
| Storage port | **[CORE]** | ADR-007; CS is its heaviest user (drawings) — streaming/quota needs may *evolve* Core via normal proposal, not fork |
| DB-backed background jobs | **[CORE]** | ADR-006 pattern; CS pipelines are jobs; if job volume outgrows it, that's a Core evolution decision |
| i18n mechanism (message keys, catalog pattern) | **[CORE]** | ADR-015; CS ships its own `cs.*` bg catalog **[MODULE]** |
| Technical audit log | **[CORE]** | login/admin trail; domain audit is **[MODULE]** ([22 §2](22_AUDIT_AND_VERSIONING.md)) |
| Health/config/logging platform services | **[CORE]** | as-is |
| Registration, subscriptions, billing (Етап 3) | **[CORE]** (planned) | CS becomes second consumer when it ships — first real test of ADR-018 as platform |
| Module activation (`company_modules` flag, nav gating) | **[CORE]** (minimal form) | exactly as BOS-06/BOS-08 Phase 5 prescribe |
| Commercial documents (invoicing) | **[SHARED]** (planned, Етап 4) | if supervision firms want invoicing later, they activate it; CS does not build billing |
| Project registry, participants/parties | **[MODULE]** | vertical vocabulary (възложител, строител…); *generic "contacts/party" platform explicitly rejected now* — BOS-00 anti-goal §7.2 |
| Knowledge base (facts, provenance, taxonomy) | **[MODULE]** | the vertical's heart |
| Document type registry | **[MODULE]** | Наредба-specific |
| Template engine (manifest model) | **[MODULE]**, **[FUTURE-X]** | BOS-08 Phase 6 names "document generation plumbing" a likely first extraction — *after* ServiceFlow's PDF path and this DOCX path both exist |
| DOCX render adapter | **[MODULE]**, **[FUTURE-X]** | same as above; keep renderer interface clean to ease later extraction |
| Rules engine | **[MODULE]**, **[UNDECIDED]** for extraction | generic-looking, but rule kinds are domain-shaped; revisit only if module #3 brings real rules |
| Workflow engine (state machines, gates) | **[MODULE]** | BOS-00 §6 non-goal: no generic workflow engine; CS is the "second workflow-shaped product bringing its own" |
| Extraction/OCR/AI pipeline | **[MODULE]**, **[UNDECIDED]** | plausible platform capability someday (any module ingesting documents); *no evidence yet* — quarantine architecture documented so extraction wouldn't require redesign |
| Document numbering/sequences | **[UNDECIDED]** | BOS-05 §1 already tracks `document_sequences` ownership for Етап 4; CS keeps module-local sequences until that resolves; must not fork a second pattern silently — coordinate in the same decision |
| Drawings & quantities | **[MODULE]** | purely vertical |
| Consistency findings model | **[MODULE]** | vertical semantics |
| Dossier & timeline | **[MODULE]** | timeline *pattern* mirrors ServiceFlow's (ADR-011 projection); the pattern is Core, the tables are module |
| Frontend shell, routing, session UI | **[CORE]** | CS is a feature area with own folder + `cs.*` catalog |
| Export format participation | **[CORE]** mechanism / **[MODULE]** content | extends ADR-012 |

## 3. Contract surface (planned, first code PR makes it real)

- CS consumes: `identity.deps` (auth/session DI), `identity.contracts`,
  `shared_kernel` (ids, db chokepoint, events, storage, i18n), platform
  health/jobs.
- CS exposes: **nothing** in v1. No other module may import
  `construction_supervision.*`; its `contracts.py` stays empty until a real
  consumer exists (BOS-04 discipline, anti-goal §7.1: no abstraction with
  one consumer).

## 4. Platform asks (explicit, so they don't happen by drift)

1. Storage port: streaming upload/download + per-tenant usage metering —
   proposal to Core when phase C sizes it (drawings).
2. Jobs: concurrency limits/priorities per queue if OCR batches starve
   interactive work — evidence first.
3. Numbering: participate in the BOS-05 §1 `document_sequences` decision.
4. Nothing else. Each new ask is a BOS-governed proposal, not a module PR
   reaching into Core.

## 5. Extraction watchlist (for BOS Phase 6, evidence to collect)

While building [MODULE] pieces, record divergence/convergence with
ServiceFlow's equivalents: document generation (PDF vs DOCX paths), numbering,
attachments/storage usage, timeline projections. When module #2 is in
production, this section becomes the input to Phase 6 extraction proposals —
per capability, one at a time, PO-gated (BOS-08).
