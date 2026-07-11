# ADR-002 Spike — PostgreSQL Hardening Gate

This folder proves that a bundled PostgreSQL can run invisibly on a shop's Windows
PC (ADR-002). **The gate blocks Alembic migration #1** — no database schema exists
until it passes on the reference VMs.

## Contents

- `pg-hardening-checklist.md` — the gate items + how to run (start here)
- `smoke-run-2026-07-10.md` — dev-workstation subset result (PASS 8/8, not the gate)
- `scripts/` — building blocks + the orchestrator
  - `Invoke-FullChecklist.ps1` — **run this on each VM**; emits a PASS/FAIL report
  - `Get-Postgres.ps1`, `New-Instance.ps1`, `Start-/Stop-Instance.ps1`,
    `Invoke-RestoreDrill.ps1`, `Register-Service.ps1`, `common.ps1`
- `harness/` — `write_loop.py` (checksummed committer) + `verify.py` (integrity)
- `.work/` — gitignored scratch (binaries, instances, and `reports/`)

## Turnkey run on a reference VM

```powershell
# prerequisites: Python 3.12+, git; clone the repo
cd backend; uv sync --dev; cd ..
powershell -ExecutionPolicy Bypass -File ops\spike\scripts\Invoke-FullChecklist.ps1
```

The report prints to the console (copy it back) and is saved under
`ops\spike\.work\reports\`. Run the extra modes for the physical items:
`MinorUpgrade`, `PrepPowerLoss`/`VerifyPowerLoss` (×10), `PrepReboot`/`VerifyReboot`.
Purely manual items are listed as MANUAL in the report with the operator action.

## Gate decision

When every reference VM reports PASS (or MANUAL items are signed off), record the
outcome in `../../docs/07_ADR_INDEX.md` (Stage-0 gate) and Stage 1 may begin with
migration #1. On any FAIL, execute the ADR-002 SQLite exit ramp instead — **before**
any schema exists.
