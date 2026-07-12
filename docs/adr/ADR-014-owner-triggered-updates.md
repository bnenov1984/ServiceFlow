# ADR-014 — Owner-Triggered Updates with Auto-Backup and Rollback

Status: **Superseded by ADR-017 (vendor-operated CD) — 11.07.2026 pivot (doc 14).
Expand–contract migrations and rehearse-before-migrate are carried into ADR-017.
Parked for the future local edition.** · Date: 10.07.2026 · Source: 04 (A6 design)

## Context
Updates must reach a fleet of independent, sometimes-offline local installations
without a technician on site, and must never destroy data or leave a shop without a
working system (04 principle).

## Decision
Updates are **never silent**: the Owner triggers them from a visible prompt. The
pipeline (04 §2) is frozen as: preconditions → migration rehearsal on the nightly
restore-verified scratch copy → maintenance mode → automatic verified pre-update
backup → side-by-side install with atomic switch (N=2 versions retained) → live
migrations → health suite → success, or **automatic rollback** (version switch-back;
restore of pre-update backup if live migrations ran — zero data loss because
maintenance mode preceded them). Releases ship on `pilot` → `stable` rings with
staged rollout and a kill switch; packages are cumulative from
`minimum-upgradable-from`; DB migrations are forward-only with expand–contract for
destructive changes.

## Alternatives considered
- **Silent auto-updates** — right for browsers, wrong for a system holding a
  business's operational data; a bad release would hit the whole fleet unattended.
  Rejected.
- **Manual package distribution (MSI by email/USB)** — unlimited support cost,
  guaranteed version fragmentation. Rejected.
- **Down-migrations for rollback** — reverse DDL on real data is riskier than
  restoring a verified backup taken seconds earlier. Rejected.

## Consequences
- **Advantages:** every update is rehearsed against the shop's own data before
  touching it; the fleet stays observable (vendor console per A4); failure is
  survivable by construction.
- **Disadvantages:** owner-triggered means stragglers — mitigated by cumulative
  packages, in-app nagging on old versions, and `minimum-upgradable-from` chaining.
- **Risks:** the updater itself is the highest-stakes code we ship. Mitigation: the
  04 §6 acceptance criteria (kill-the-process drill et al.) are a release gate for
  every updater change.

## Reconsideration triggers
SaaS edition (vendor-operated hosting) makes this pipeline the local-edition path
only; PATCH-level auto-apply may be revisited after 12+ months of fleet stability data.
