# Downloads and extracts the PostgreSQL zip distribution (checklist: "Silent install").
. (Join-Path $PSScriptRoot "common.ps1")

New-Item -ItemType Directory -Force $WorkDir | Out-Null
$zip = Join-Path $WorkDir "postgresql-$PgVersion.zip"

if (-not (Test-Path $zip)) {
    Write-Host "Downloading $PgZipUrl ..."
    # BITS is flaky on fresh VMs; plain WebClient is fine for a one-shot fetch.
    (New-Object System.Net.WebClient).DownloadFile($PgZipUrl, $zip)
}
Write-Host ("Zip size: {0:N0} MB" -f ((Get-Item $zip).Length / 1MB))

if (-not (Test-Path $PgBin)) {
    Write-Host "Extracting ..."
    Expand-Archive -Path $zip -DestinationPath $WorkDir -Force
    # The zip contains a top-level 'pgsql' folder, which matches $PgHome.
}
Assert-PgBinaries
& (Join-Path $PgBin "initdb.exe") --version
Write-Host "OK: binaries ready at $PgBin"
