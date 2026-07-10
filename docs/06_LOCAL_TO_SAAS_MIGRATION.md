# 06 — Local → SaaS Migration Workflow (A8)

Status: **Approved by Product Owner 10.07.2026** · Date: 10.07.2026
Design document. The workflow itself ships with SaaS (V2); **its constraints bind V1
today** — that is this document's real payload (§2).

---

## 1. Business promise

A local customer moves to the cloud edition **without losing a single order, photo,
invoice or timeline entry**, with downtime measured in minutes, and with a safe abort
at every step before cutover. Migration is a product feature, not a consulting
engagement.

## 2. Constraints imposed on V1 (binding design rules)

These exist so that §3 is *possible later without rewriting V1*. They cost almost
nothing now and everything if skipped:

- C1 **Globally unique identifiers** (UUID-class) for every domain record from the
  first migration — SaaS import needs zero ID remapping and zero collision risk.
  Human numbers (order №, invoice №) stay per-company sequences and transfer as-is.
- C2 **The versioned export format is the backup artifact** (05 §1). The SaaS
  importer consumes exactly what the restore-verifier proves nightly. Migration
  correctness is therefore *rehearsed every night in every shop* — this is the
  design's keystone.
- C3 `company_id` on every record (03 §6) — locally constant, cloud-meaningful.
- C4 **No absolute filesystem paths in domain data** — attachments referenced by
  storage keys through the storage port (fs locally, S3-class in cloud).
- C5 **Portable credentials:** standard password hashing (argon2id-class) so user
  accounts and PINs transfer without forced resets.
- C6 All timestamps stored timezone-aware (UTC); Europe/Sofia is presentation.
- C7 Format version embedded in every artifact; the SaaS importer maintains an
  upgrade chain for **all** published format versions (same discipline as DB
  migrations — an old shop's artifact must import forever).
- C8 No local-only semantics inside domain modules (license, tray, updater live in
  `platform`, which SaaS replaces wholesale).

## 3. The migration workflow (V2 feature, designed now)

```
PHASE 0 — ELIGIBILITY   Owner in local app: „Преминаване към облак" → app checks:
  version current · health green · last artifact verified → creates/links SaaS
  account via License API (vendor console sees intent)

PHASE 1 — TRANSFER      Fresh full artifact produced → resumable, encrypted upload
  to SaaS import endpoint → LOCAL SHOP KEEPS WORKING NORMALLY (artifact is a
  snapshot; nothing is locked)

PHASE 2 — STAGED IMPORT SaaS validates (signature, checksums, format version →
  upgrade chain) → imports into a NEW ISOLATED TENANT in staging state → runs the
  full verification suite from 05 §4 (counts, invariants, gapless invoices, file
  checksums) → produces verification report

PHASE 3 — REVIEW        Owner opens the staged cloud tenant READ-ONLY in a browser,
  side by side with the live local app → sees the report („4 812 поръчки, 138 GB…")
  → ABORT here = staged tenant deleted, nothing changed locally (repeatable)

PHASE 4 — DELTA + CUTOVER (the only downtime) Owner confirms → local app enters
  maintenance mode → small delta artifact (changes since Phase 1 snapshot) uploads
  and applies → final verification → local app switches to „Мигрирано" mode →
  users land on the cloud URL; sessions/passwords/PINs work (C5)

PHASE 5 — AFTERCARE     Local install: permanent READ-ONLY archive mode with a
  banner linking to the cloud (kept ≥ 90 days, then Owner may uninstall; a final
  local artifact is written to the backup destinations regardless) → local license
  converts to SaaS subscription on the vendor side, same commercial identity
```

Downtime = Phase 4 only; delta model keeps it to minutes. Every phase before 4 is
abortable with zero consequence.

## 4. Edge cases

| Case | Design answer |
|---|---|
| Huge photo sets on slow uplink | Phase 1 is resumable and can run for days while the shop works; delta stays small. Offline pre-seed (artifact on disk shipped/uploaded from elsewhere) supported by the same format |
| Upload interrupted repeatedly | Content-addressed chunks; resume forever; no restart-from-zero |
| Shop edits during Phase 2/3 | Expected — delta in Phase 4 captures it |
| Verification mismatch in Phase 2 | Import refused, report to vendor diagnostics, local unaffected — this failure mode is why C2 (nightly rehearsal) makes it near-impossible |
| Two local installs, one business | Out of scope for V2 launch: one local → one tenant. Merging is a future consulting-grade feature; documented, not promised |
| Cold feet after cutover | SaaS → local return is **not** promised as a product feature. GDPR/company export always available from SaaS (same format); a manual re-import to a fresh local install is technically the same pipeline, documented as best-effort |
| License/billing overlap | Vendor console converts the subscription at cutover; no double-charging by design; grace overlap of one billing period |

## 5. What this document deliberately does not decide

Cloud topology, tenant isolation enforcement, SaaS pricing, and the SaaS onboarding
UX are V2 architecture work. This document only guarantees that **V1's data design
cannot paint us out of that future** — via C1–C8, which are hereby part of V1's
architecture freeze.

## 6. Acceptance criteria (bound to V1 despite being a V2 feature)

1. C1–C8 are enforced by V1 ADRs and checked in V1 code review rules.
2. From V1's first release onward, any nightly artifact can be imported into a
   reference cloud environment in CI (a thin importer harness exists before SaaS
   does — it is the same restore path as 05).
3. Format version bumps ship with an importer upgrade step + test artifact, every
   time, no exceptions.
