# Stage-0 Gate: Bundled PostgreSQL Hardening Spike (ADR-002)

**This gate blocks Alembic migration #1.** Pass all items on both reference VMs
(Win 10 + Win 11, HDD + SSD variants, 8 GB RAM floor) or execute the SQLite ramp
(ADR-002) before any schema exists.

## Setup under test
PostgreSQL 16 binaries (zip distribution, not the EDB interactive installer),
private instance: own data dir under the app's data root, own port (auto-picked,
non-default), locale `bg_BG`/UTF-8, service registered via `pg_ctl register`
(runs as a low-privilege service account), app is the only client (localhost only).

## Checklist

### Silent install
- [ ] Scripted: unzip → initdb → register service → start → app connects. Zero
      prompts, zero PATH/registry pollution, no conflict with any existing
      PostgreSQL on the machine (port + service name uniqueness).
- [ ] Uninstall removes the service cleanly, preserves the data dir.

### Power-loss survival
- [ ] 10× hard VM power-off during active writes (a write-loop harness) → service
      auto-starts, WAL recovery completes, data consistent (harness verifies its
      own checksums), health reports green without human action.
- [ ] Power-off during a backup run → next backup succeeds, failed artifact not
      counted (05 rules).

### Unattended minor upgrade
- [ ] Scripted binary swap 16.x → 16.y with service stop/start, no initdb, data
      intact. Measured downtime < 60 s.

### Restore drill
- [ ] pg_dump → drop instance → fresh initdb → pg_restore → app connects, data
      intact. Scripted end-to-end (this script grows into the 05 restore wizard).

### Environmental hostility
- [ ] Windows Update reboot while running → clean recovery on boot.
- [ ] Defender real-time scanning enabled with our planned exclusions → no
      corruption, acceptable write latency.
- [ ] Disk-full during writes → PostgreSQL degrades per its design, app health
      turns red with the right message, recovery after space freed.
- [ ] Machine sleep/wake → connections recover (app-side retry policy verified).

## Exit
- **PASS:** record results here, close the gate in 07_ADR_INDEX, migration #1 may
  exist.
- **FAIL (any unfixable item):** execute ADR-002 SQLite ramp; amend ADR-002 with
  findings; the deadline is *before* the first migration, *never* after first
  customer data.
