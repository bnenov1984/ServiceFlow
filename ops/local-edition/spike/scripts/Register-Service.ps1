# Checklist "Silent install": register the instance as an auto-start Windows service.
# REQUIRES ELEVATION - run on the reference VM as Administrator.
param(
    [Parameter(Mandatory)] [string]$Name
)
. (Join-Path $PSScriptRoot "common.ps1")
Assert-PgBinaries

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Service registration requires an elevated shell (VM step, not dev-machine step)."
}

$dataDir = Get-InstanceDir $Name
$svcName = "ServiceFlow-PG-$Name"
& (Join-Path $PgBin "pg_ctl.exe") register -N $svcName -D $dataDir -S auto -w
if ($LASTEXITCODE -ne 0) { throw "pg_ctl register failed" }
Start-Service $svcName
Write-Host "OK: service '$svcName' registered (auto-start) and running"
