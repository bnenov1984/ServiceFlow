# Stage-0 Gate: Bundled PostgreSQL Hardening Spike (ADR-002)

**This gate blocks Alembic migration #1.** Pass all items on both reference VMs
(Win 10 + Win 11, HDD + SSD variants, 8 GB RAM floor) or execute the SQLite ramp
(ADR-002) before any schema exists.

## Setup under test
PostgreSQL 16 binaries (zip distribution, not the EDB interactive installer),
private instance: own data dir under the app's data root, own port (auto-picked,
non-default), locale `bg_BG`/UTF-8, service registered via `pg_ctl register`
(runs as a low-privilege service account), app is the only client (localhost only).

## How to run on a reference VM (turnkey)

One-time per VM: install Python 3.12+ and git, clone the repo, then:

```powershell
cd backend; uv sync --dev; cd ..    # harness needs psycopg
# full automatable battery + a machine-readable PASS/FAIL report:
powershell -ExecutionPolicy Bypass -File ops\spike\scripts\Invoke-FullChecklist.ps1
```

The orchestrator (`Invoke-FullChecklist.ps1`) runs every software-automatable item
and prints a report to copy back. The remaining items are Prep/Verify pairs so even
the physical ones are objective:

```powershell
# real minor upgrade 16.10 -> 16.11 (fully automatic):
... Invoke-FullChecklist.ps1 -Mode MinorUpgrade

# hard power-off, 10 cycles: Prep -> pull power from hypervisor -> boot -> Verify
... Invoke-FullChecklist.ps1 -Mode PrepPowerLoss      # then hard power-off
... Invoke-FullChecklist.ps1 -Mode VerifyPowerLoss    # after boot; repeat x10

# service reboot survival (elevated PowerShell):
... Invoke-FullChecklist.ps1 -Mode PrepReboot         # then reboot VM
... Invoke-FullChecklist.ps1 -Mode VerifyReboot
```

Purely manual items the report lists as MANUAL (uninstall-keeps-data, Windows Update
reboot, Defender interaction, disk-full, sleep/wake) have their operator action in
the report's Detail column.

## How to run individual steps (scripts in `scripts/`, harness in `harness/`)

```powershell
# one-time
.\scripts\Get-Postgres.ps1                                   # download + extract 16.11
.\scripts\New-Instance.ps1 -Name spike-a -Port 5599          # initdb + private config
.\scripts\Start-Instance.ps1 -Name spike-a

# integrity harness (from backend/, uses its venv)
uv run python ..\ops\spike\harness\write_loop.py --port 5599 --duration 30
uv run python ..\ops\spike\harness\verify.py --port 5599

# crash-adjacent stop (VM power-off is the real test) + recovery check
.\scripts\Stop-Instance.ps1 -Name spike-a -Immediate
.\scripts\Start-Instance.ps1 -Name spike-a                   # WAL recovery
uv run python ..\ops\spike\harness\verify.py --port 5599

# restore drill (dump -> fresh instance -> restore -> verify)
.\scripts\Invoke-RestoreDrill.ps1 -SourceName spike-a -SourcePort 5599

# VM only (elevated): service registration + reboot survival
.\scripts\Register-Service.ps1 -Name spike-a
```

For the power-loss items: run `write_loop.py` with no `--duration`, hard power-off
the VM from the hypervisor, boot, `Start-Instance` (or service auto-start), then
`verify.py`. Repeat 10×.

## Checklist

### Silent install
- [x] *(local subset, 10.07.2026 — see smoke-run-2026-07-10.md)* Scripted: unzip →
      initdb → start → connect. Zero prompts. **VM part pending:** service
      registration, PATH/registry cleanliness audit, coexistence with an existing
      PostgreSQL.
- [ ] Uninstall removes the service cleanly, preserves the data dir.

### Power-loss survival
- [x] *(crash-adjacent local proxy PASS: `pg_ctl -m immediate` under active load →
      WAL recovery, 0 corrupt, 0 lost acknowledged writes)* **VM part pending:**
      10× hard hypervisor power-off → service auto-starts, health green unattended.
- [ ] Power-off during a backup run → next backup succeeds, failed artifact not
      counted (05 rules).

### Unattended minor upgrade
- [ ] Scripted binary swap 16.x → 16.y with service stop/start, no initdb, data
      intact. Measured downtime < 60 s.

### Restore drill
- [x] *(local PASS, 75 890 rows verified)* pg_dump → fresh initdb → pg_restore →
      verify, scripted end-to-end (`Invoke-RestoreDrill.ps1` — grows into the 05
      restore wizard). **VM re-run happens as part of the matrix anyway.**

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
