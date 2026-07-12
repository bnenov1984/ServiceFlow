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

# Isolated pg_ctl start. Direct 'pg_ctl start' lets the postgres daemon inherit the
# caller's stdout pipe, hanging any surrounding PowerShell pipeline forever (smoke-run
# finding #1). Always start through this: private redirected handles + handle-cached
# WaitForExit (PS 5.1 returns $null ExitCode otherwise). Reuse everywhere.
function Invoke-PgCtlStart {
    param([Parameter(Mandatory)][string]$BinDir, [Parameter(Mandatory)][string]$DataDir)
    $out = Join-Path $DataDir "pgctl-start.out"
    $err = Join-Path $DataDir "pgctl-start.err"
    $p = Start-Process -FilePath (Join-Path $BinDir "pg_ctl.exe") `
        -ArgumentList @("-D", "`"$DataDir`"", "-l", "`"$(Join-Path $DataDir 'server.log')`"", "-w", "start") `
        -PassThru -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err
    $null = $p.Handle
    $null = $p.WaitForExit(120000)
    if (-not $p.HasExited) { throw "pg_ctl start did not finish within 120s ($DataDir)" }
    if ($p.ExitCode -ne 0) { Get-Content $err | Write-Host; throw "pg_ctl start failed (exit $($p.ExitCode)) - see $DataDir\server.log" }
}
