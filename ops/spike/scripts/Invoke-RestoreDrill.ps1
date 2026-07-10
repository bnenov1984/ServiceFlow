# Checklist "Restore drill": dump instance A -> fresh instance B -> restore -> verify.
# This script is the seed of the 05 restore wizard.
param(
    [Parameter(Mandatory)] [string]$SourceName,
    [Parameter(Mandatory)] [int]$SourcePort,
    [int]$TargetPort = 5601
)
. (Join-Path $PSScriptRoot "common.ps1")
Assert-PgBinaries

$env:PGPASSWORD = "spike-only-password"
$dump = Join-Path $WorkDir "drill.dump"

Write-Host "1/4 pg_dump from '$SourceName' (port $SourcePort) ..."
& (Join-Path $PgBin "pg_dump.exe") -h localhost -p $SourcePort -U serviceflow -Fc -f $dump postgres
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }

Write-Host "2/4 fresh target instance ..."
$target = "drill-target-$(Get-Random)"
& (Join-Path $PSScriptRoot "New-Instance.ps1") -Name $target -Port $TargetPort
& (Join-Path $PSScriptRoot "Start-Instance.ps1") -Name $target

Write-Host "3/4 pg_restore ..."
& (Join-Path $PgBin "pg_restore.exe") -h localhost -p $TargetPort -U serviceflow -d postgres $dump
if ($LASTEXITCODE -ne 0) { throw "pg_restore failed" }

Write-Host "4/4 verify (harness) ..."
Push-Location (Join-Path $SpikeRoot "..\..\backend")
uv run python ..\ops\spike\harness\verify.py --port $TargetPort
$verifyExit = $LASTEXITCODE
Pop-Location

& (Join-Path $PSScriptRoot "Stop-Instance.ps1") -Name $target
if ($verifyExit -ne 0) { throw "DRILL FAILED: restored data did not verify" }
Write-Host "OK: restore drill passed (source '$SourceName' -> '$target')"
