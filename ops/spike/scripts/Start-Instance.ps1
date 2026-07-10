param([Parameter(Mandatory)] [string]$Name)
. (Join-Path $PSScriptRoot "common.ps1")
Assert-PgBinaries
$dataDir = Get-InstanceDir $Name

# Two Windows pitfalls, both found during the smoke run:
# 1. Calling pg_ctl directly makes the postgres daemon inherit the caller's stdout
#    pipe; any PowerShell pipeline around the calling script then hangs on EOF.
#    -> Start-Process with redirected files gives pg_ctl private handles.
# 2. PS 5.1 'Start-Process -Wait' waits for the whole process TREE (the daemon),
#    never returning. -> .WaitForExit() waits for pg_ctl alone.
$out = Join-Path $dataDir "pgctl-start.out"
$err = Join-Path $dataDir "pgctl-start.err"
$p = Start-Process -FilePath (Join-Path $PgBin "pg_ctl.exe") `
    -ArgumentList @("-D", "`"$dataDir`"", "-l", "`"$(Join-Path $dataDir 'server.log')`"", "-w", "start") `
    -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $out -RedirectStandardError $err
$null = $p.Handle  # PS 5.1: without caching the handle, ExitCode reads back $null
$null = $p.WaitForExit(120000)
if (-not $p.HasExited) { throw "pg_ctl start did not finish within 120s" }
if ($p.ExitCode -ne 0) {
    Get-Content $err | Write-Host
    throw "pg_ctl start failed (exit $($p.ExitCode)) - see $dataDir\server.log"
}
Write-Host "OK: instance '$Name' running"
