# Creates a private instance: initdb + locked-down config (checklist: "Silent install").
param(
    [Parameter(Mandatory)] [string]$Name,
    [Parameter(Mandatory)] [int]$Port
)
. (Join-Path $PSScriptRoot "common.ps1")
Assert-PgBinaries

$dataDir = Get-InstanceDir $Name
if (Test-Path $dataDir) { throw "Instance '$Name' already exists at $dataDir" }
New-Item -ItemType Directory -Force $Instances | Out-Null

# Password auth from the first byte; the installer generates this per machine (11 par.3).
$pwFile = Join-Path $WorkDir "$Name.pw"
Set-Content -Path $pwFile -Value "spike-only-password" -Encoding ascii -NoNewline

# --data-checksums: detect silent disk corruption early (shop-PC disks; smoke-run finding).
& (Join-Path $PgBin "initdb.exe") -D $dataDir -U serviceflow -A scram-sha-256 `
    --pwfile $pwFile -E UTF8 --locale=C --data-checksums
if ($LASTEXITCODE -ne 0) { throw "initdb failed" }

# Private instance: localhost only, own port, sized for a shop PC (8 GB floor).
# timezone=UTC: storage is UTC by constraint C6; never inherit the OS guess.
Add-Content -Path (Join-Path $dataDir "postgresql.conf") -Encoding ascii -Value @"

# --- ServiceFlow spike overrides ---
port = $Port
listen_addresses = 'localhost'
shared_buffers = 256MB
max_connections = 30
timezone = 'UTC'
"@

Write-Host "OK: instance '$Name' created on port $Port at $dataDir"
