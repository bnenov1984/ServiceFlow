# Shared paths/config for the ADR-002 spike scripts. Dot-source from the others.
$ErrorActionPreference = "Stop"

$SpikeRoot = Split-Path -Parent $PSScriptRoot          # ops/spike
$WorkDir   = Join-Path $SpikeRoot ".work"              # gitignored scratch area
$PgVersion = "16.11-1"
$PgZipUrl  = "https://get.enterprisedb.com/postgresql/postgresql-$PgVersion-windows-x64-binaries.zip"
$PgHome    = Join-Path $WorkDir "pgsql"                # extracted binaries (bin\ inside)
$PgBin     = Join-Path $PgHome "bin"
$Instances = Join-Path $WorkDir "instances"

function Assert-PgBinaries {
    if (-not (Test-Path (Join-Path $PgBin "initdb.exe"))) {
        throw "PostgreSQL binaries not found at $PgBin - run Get-Postgres.ps1 first"
    }
}

function Get-InstanceDir([string]$Name) { Join-Path $Instances $Name }
