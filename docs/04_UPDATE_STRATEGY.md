# 04 — Update Strategy (A6)

Status: **Approved by Product Owner 10.07.2026** · Date: 10.07.2026
Design document — process and guarantees, no implementation.
Principle: **an update must never be able to destroy a shop's data or leave it
without a working system.** Every guarantee below exists to serve that sentence.

---

## 1. Release model (vendor side)

- **Versioning:** semantic (`MAJOR.MINOR.PATCH`). MAJOR = migration/compatibility
  milestones; MINOR = features; PATCH = fixes.
- **Package:** one signed archive per release: application, frontend assets, ordered
  DB migrations, optional bundled-PostgreSQL upgrade unit, Bulgarian release notes,
  manifest (version, checksums, minimum-upgradable-from version, required disk space).
- **Feed:** static signed manifest (JSON) + packages on CDN — the "update feed" from
  03 §4. No dynamic vendor logic needed to serve updates.
- **Rings:** `pilot` (friendly shops, opt-in) → `stable`. Staged rollout by
  percentage within `stable`; **kill switch** = pulling the release from the manifest
  (already-updated installs are unaffected; rollback advisory possible via console).
- **Cumulative packages:** a shop offline for six months updates in one step —
  packages contain everything needed from `minimum-upgradable-from`; migrations are
  ordered and idempent-checked, so multi-version jumps are the same code path as
  single steps.

## 2. Update flow (shop side)

```
Daily job: check feed → new version? → tray + settings: „Налична е нова версия"
→ OWNER clicks „Обнови" (never silent — PO directive)
→ PRECONDITIONS: health green · disk space ≥ manifest requirement · verified backup
  age acceptable · signature valid · version chain valid
→ MIGRATION REHEARSAL: apply new migrations to the nightly restore-verification
  scratch copy first (see 05) → failure = abort before touching live, auto-report
→ MAINTENANCE MODE: active users see „Обновяване, ~N минути" banner; new writes off
→ AUTOMATIC PRE-UPDATE BACKUP: full artifact, restore-verified (05 fast-verify path)
→ APPLY: new version installed side-by-side (previous N=2 versions retained) →
  atomic switch → DB migrations on live → warm-up
→ HEALTH SUITE: app up · DB schema at target · smoke checks (login, order list,
  PDF render, search) 
→ SUCCESS: exit maintenance, show release notes, report version to vendor
→ FAILURE at any point: AUTOMATIC ROLLBACK — switch back to previous version;
  if live migrations already ran: restore pre-update backup (zero data loss —
  maintenance mode means no writes happened after it) → red health + support
  package offered → vendor notified (if telemetry opted in)
```

## 3. Database migration policy

- Forward-only, ordered, numbered; no down-migrations in production (rollback =
  restore, which is safer than reverse DDL on real data).
- **Expand–contract for destructive changes:** release N adds/backfills, release N+1
  removes. No release both adds and destroys the same structure.
- Every migration ships with a rehearsal assertion set (row-count preservation,
  invariant spot checks) executed during the rehearsal step.
- Bundled PostgreSQL engine upgrades are rare, packaged as explicit "platform
  updates" with their own longer maintenance window and mandatory fresh backup.

## 4. Failure scenarios

| Scenario | Design answer |
|---|---|
| Power loss mid-update | Package fully staged before the atomic switch; boot-time check detects incomplete switch → completes or rolls back automatically |
| Disk fills during update | Precondition blocks start; staging area sized from manifest |
| Antivirus quarantines new binaries | Signed binaries + installer-applied exclusions; health suite catches it → rollback |
| Migration bug that rehearsal missed | Pre-update backup restore; incident flows to vendor via support package |
| Shop skips a year of updates | Cumulative package + `minimum-upgradable-from`; if below minimum, chained double-update guided by the updater |
| Update during business hours by accident | Maintenance-mode confirmation shows logged-in user count; Owner confirms explicitly |

## 5. Vendor console (A4 scope)

Per install: current version, ring, last check-in, update history, failed-update
alerts. Actions: pin version (hold a problem shop), advise rollback, attach release
note. Fleet view: version distribution — the answer to "can we retire migration X?".

## 6. Acceptance criteria (release gate for the updater itself)

1. Kill the process at any step of a test update → system boots into a working
   version with intact data, every time.
2. Update from oldest supported version and from previous version — both green.
3. Rollback drill (forced health failure) completes unattended.
4. A failed update leaves a support package ready to send.
5. Total Owner-visible downtime for a routine PATCH ≤ 5 minutes on reference hardware.

Open question: none — A6 design is self-contained; parameters (ring sizes, N retained
versions) are tunables, not decisions.
