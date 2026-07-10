param(
    [Parameter(Mandatory)] [string]$Name,
    [switch]$Immediate  # -Immediate simulates an unclean stop (crash-adjacent, not power loss)
)
. (Join-Path $PSScriptRoot "common.ps1")
Assert-PgBinaries
$dataDir = Get-InstanceDir $Name
$mode = "fast"
if ($Immediate) { $mode = "immediate" }
& (Join-Path $PgBin "pg_ctl.exe") -D $dataDir -m $mode -w stop
Write-Host "OK: instance '$Name' stopped ($mode)"
