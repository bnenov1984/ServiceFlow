param([Parameter(Mandatory)] [string]$Name)
. (Join-Path $PSScriptRoot "common.ps1")
Assert-PgBinaries
Invoke-PgCtlStart -BinDir $PgBin -DataDir (Get-InstanceDir $Name)
Write-Host "OK: instance '$Name' running"
