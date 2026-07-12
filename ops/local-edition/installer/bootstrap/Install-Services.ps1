# Post-install bootstrap (walking skeleton). Idempotent: safe to re-run.
# Called by the installer elevated. Fails loudly - the installer surfaces errors.
param(
    [Parameter(Mandatory)] [string]$DataRoot
)
$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot   # {app}
$PgBin = Join-Path $AppRoot "pgsql\bin"
$PgData = Join-Path $DataRoot "data\pg"
$PgPort = 5710  # private, non-default; collision check below

# 1. Private PostgreSQL instance (only on first install).
if (-not (Test-Path (Join-Path $PgData "PG_VERSION"))) {
    if (Get-NetTCPConnection -LocalPort $PgPort -ErrorAction SilentlyContinue) {
        throw "Port $PgPort is taken - aborting instead of guessing (support package will say why)."
    }
    $pw = -join ((48..57) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    $pwFile = Join-Path $env:TEMP "sfpg.tmp"
    Set-Content -Path $pwFile -Value $pw -Encoding ascii -NoNewline
    & (Join-Path $PgBin "initdb.exe") -D $PgData -U serviceflow -A scram-sha-256 --pwfile $pwFile -E UTF8 --locale=C --data-checksums
    if ($LASTEXITCODE -ne 0) { throw "initdb failed" }
    Remove-Item $pwFile -Force -Confirm:$false
    Add-Content -Path (Join-Path $PgData "postgresql.conf") -Encoding ascii -Value "`nport = $PgPort`nlisten_addresses = 'localhost'`nshared_buffers = 256MB`nmax_connections = 30`ntimezone = 'UTC'"
    # Machine-local secrets file, ACL-restricted (11 par.3).
    $secrets = Join-Path $DataRoot "secrets.json"
    Set-Content -Path $secrets -Encoding ascii -Value ("{{""database_url"": ""postgresql+psycopg://serviceflow:{0}@localhost:{1}/postgres""}}" -f $pw, $PgPort)
    icacls $secrets /inheritance:r /grant "SYSTEM:F" /grant "Administrators:F" | Out-Null
}

# 2. Services (idempotent re-register).
$pgSvc = "ServiceFlow-PG"
if (-not (Get-Service $pgSvc -ErrorAction SilentlyContinue)) {
    & (Join-Path $PgBin "pg_ctl.exe") register -N $pgSvc -D $PgData -S auto -w
    if ($LASTEXITCODE -ne 0) { throw "pg_ctl register failed" }
}
Start-Service $pgSvc

$appSvcExe = Join-Path $AppRoot "tray\serviceflow-app-svc.exe"  # WinSW wrapper
if (-not (Get-Service "ServiceFlow-App" -ErrorAction SilentlyContinue)) {
    & $appSvcExe install
    if ($LASTEXITCODE -ne 0) { throw "app service install failed" }
}
Start-Service "ServiceFlow-App"

# 3. LAN firewall rule (app port only; PG stays localhost-only).
if (-not (Get-NetFirewallRule -DisplayName "ServiceFlow LAN" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "ServiceFlow LAN" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private | Out-Null
}

# 4. Health poll before declaring success.
$deadline = (Get-Date).AddSeconds(60)
do {
    try {
        $r = Invoke-RestMethod "http://localhost:8080/api/v1/platform/health" -TimeoutSec 3
        if ($r.status -in @("ok", "degraded")) { Write-Host "Bootstrap OK: health=$($r.status)"; exit 0 }
    } catch { Start-Sleep -Seconds 2 }
} while ((Get-Date) -lt $deadline)
throw "App did not become healthy within 60s"
