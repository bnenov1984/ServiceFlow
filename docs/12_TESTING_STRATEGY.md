# 12 — Testing Strategy

Status: **Approved by Product Owner 10.07.2026** · Date: 10.07.2026 · Basis: 04 §6, 05 §7, frozen docs
Sized for one developer: a small set of tests that **must never break**, automated
drills for the dangerous machinery, and nothing decorative.

## 1. The P0 list (regressions here block any release)

1. **Status transition matrix** (02 §2) — exhaustive table-driven tests, every cell.
2. **Invoice numbering** — gapless under concurrent issue; annul+reissue chains;
   issued-immutability (mutations → 409).
3. **Money math** — line totals, VAT modes, payments/refunds/balance derivation
   (BR-3), rounding.
4. **Backup → verify → restore** — the 05 §7 drills, automated.
5. **Updater** — the 04 §6 kill-the-process drills, automated on reference VM.
6. **Attribution** — every mutation carries the right acting user through PIN
   switches; timeline completeness for the event catalog (01 §5).
7. **Search normalization** — Cyrillic/Latin, phone/IMEI/VIN forms (ADR-010 rules as
   pure-function tests).
8. **Artifact format** — every published format version imports via the CI harness
   (ADR-012 / 06 §6.2), forever.

## 2. Test layers (pragmatic pyramid)

- **Domain unit tests** (fast, no I/O): transition matrix, money, normalization,
  approval rules, warranty-return linking. The bulk of the suite.
- **API integration tests** against real bundled-version PostgreSQL (Docker in dev/CI
  — ADR-005 keeps Docker for development): auth/PIN flows, permission matrix (02
  §12), concurrency (row_version 409s), read-only mode (423s), one test per endpoint
  group's happy path + its business errors. No mocked databases — the DB is part of
  the product.
- **E2E (Playwright), small and ruthless:** the five journeys below, desktop + one
  mobile viewport, including **print output snapshots** (протокол/фактура render —
  a broken протокол is a launch blocker, 10 §5).
- **Platform drills** (scheduled + pre-release, on a Windows reference VM):
  install → restore → update → rollback → bare-metal, per 04/05 acceptance criteria.

## 3. The five E2E journeys

1. **Intake-to-delivery:** нова поръчка (new customer+asset) → протокол print →
   диагноза + одобрение → части received → ремонт → готова → delivery dialog
   (аксесоари, плащане, гаранция) → предадена → timeline complete.
2. **Rejection path:** оценка → отказ (reason) → такса диагностика invoice → плащане
   → отказана; протокол print from terminal state.
3. **Invoice lifecycle:** draft from lines → issue (number) → annul (reason) →
   reissue → payments across both; PDF renders.
4. **Kanban concurrency:** two sessions, same card — second mover gets conflict
   toast, board reconciles; PIN switch mid-flow attributes correctly.
5. **Ops loop:** backup now → verify green → restore to fresh instance → data
   intact → update apply (test package) → health green.

## 4. CI & cadence

Every push: lint, types, domain + API suites (< 10 min budget — a slow suite gets
skipped by a solo dev, so speed is a feature). Nightly: E2E + artifact-import
harness. Pre-release: full platform drills on the reference VM matrix (minimum:
Win 10 and Win 11, HDD and SSD, 8 GB RAM floor). A release checklist in the repo
walks the gates in order — 04 §6, 05 §7, P0 green, accountant sign-off flag for any
release touching `commercial`.

## 5. Test data

One realistic Bulgarian seed fixture (shared with the sample-data feature if V1
keeps it): ~30 customers, mixed asset types, orders across all statuses incl.
terminal + warranty-return chains, an annulled invoice, refunds. Every bug fixed
gets a regression test in the layer where it bit. No coverage-percentage targets —
the P0 list is the contract, coverage numbers are vanity at this team size.
