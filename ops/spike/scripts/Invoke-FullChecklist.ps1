<#
.SYNOPSIS
  ADR-002 gate orchestrator. Run on each reference VM; produces a PASS/FAIL report
  (JSON + Markdown) to hand back for gate consolidation.

.DESCRIPTION
  Modes:
    Battery        (default) all software-automatable checklist items end-to-end.
    MinorUpgrade   real 16.10 -> 16.11 binary swap on one data dir, no initdb.
    PrepReboot     register service + marker, then you reboot the VM.
    VerifyReboot   after reboot: confirm service auto-started + data intact.
    PrepPowerLoss  start a committing writer + marker, then hard power-off from
                   the hypervisor.
    VerifyPowerLoss after boot: WAL recovery + 0 corrupt; repeat 10x.

  Physical steps (hypervisor power-off, Windows Update, sleep/wake) cannot be
  triggered from inside the guest by design - the Prep/Verify pair makes them
  objective anyway. Everything this script cannot prove itself is reported as
  MANUAL with the exact operator action, never as PASS.

.EXAMPLE
  # one-time on the VM:
  cd backend; uv sync --dev; cd ..
  powershell -ExecutionPolicy Bypass -File ops\spike\scripts\Invoke-FullChecklist.ps1
#>
[CmdletBinding()]
param(
    [ValidateSet("Battery", "MinorUpgrade", "PrepReboot", "VerifyReboot",
        "PrepPowerLoss", "VerifyPowerLoss")]
    [string]$Mode = "Battery",
    [int]$Port = 5599,
    [string]$Name = "checklist",
    [int]$WriteSeconds = 20
)
. (Join-Path $PSScriptRoot "common.ps1")

$ReportsDir = Join-Path $WorkDir "reports"
New-Item -ItemType Directory -Force $ReportsDir | Out-Null
$MarkerFile = Join-Path $WorkDir "checklist-state.json"
$script:Results = @()

function Add-Result {
    param([string]$Item, [ValidateSet("PASS", "FAIL", "MANUAL", "INFO")] [string]$Result, [string]$Detail)
    $Detail = ($Detail -replace "\s*[\r\n]+\s*", " ").Trim()  # keep report table one-line-per-row
    $script:Results += [pscustomobject]@{ item = $Item; result = $Result; detail = $Detail }
    $color = @{ PASS = "Green"; FAIL = "Red"; MANUAL = "Yellow"; INFO = "Cyan" }[$Result]
    Write-Host ("[{0,-6}] {1} - {2}" -f $Result, $Item, $Detail) -ForegroundColor $color
}

function Get-VenvPython {
    $py = Join-Path $SpikeRoot "..\..\backend\.venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        throw "Backend venv not found. Run 'uv sync --dev' in backend\ first (harness needs psycopg)."
    }
    return (Resolve-Path $py).Path
}

function Invoke-Harness {
    param([string]$Script, [string]$ArgLine)
    $py = Get-VenvPython
    $full = Join-Path $SpikeRoot "harness\$Script"
    $out = & $py $full $ArgLine.Split(" ") 2>&1 | Out-String
    return @{ ExitCode = $LASTEXITCODE; Output = $out.Trim() }
}

function Write-Report {
    $host_name = $env:COMPUTERNAME
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $os = (Get-CimInstance Win32_OperatingSystem).Caption
    $disk = (Get-CimInstance Win32_DiskDrive | Select-Object -First 1).MediaType
    $ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)

    $summary = $script:Results | Group-Object result | ForEach-Object { "$($_.Name)=$($_.Count)" }
    $payload = [pscustomobject]@{
        host = $host_name; os = $os; disk_media = $disk; ram_gb = $ram
        mode = $Mode; timestamp = $stamp; pg_version = $PgVersion
        results = $script:Results
    }
    $jsonPath = Join-Path $ReportsDir "report-$host_name-$Mode-$stamp.json"
    $mdPath = Join-Path $ReportsDir "report-$host_name-$Mode-$stamp.md"
    $payload | ConvertTo-Json -Depth 5 | Set-Content -Path $jsonPath -Encoding utf8

    $md = @()
    $md += "# ADR-002 Checklist Report"
    $md += ""
    $md += "- Host: $host_name"
    $md += "- OS: $os"
    $md += "- Disk media: $disk | RAM: $ram GB | PG: $PgVersion"
    $md += "- Mode: $Mode | Timestamp: $stamp"
    $md += "- Summary: $($summary -join ' ')"
    $md += ""
    $md += "| Item | Result | Detail |"
    $md += "|------|--------|--------|"
    foreach ($r in $script:Results) { $md += "| $($r.item) | **$($r.result)** | $($r.detail) |" }
    $md -join "`n" | Set-Content -Path $mdPath -Encoding utf8

    Write-Host "`n===== REPORT (copy this back) =====" -ForegroundColor Magenta
    Get-Content $mdPath | Write-Host
    Write-Host "`nSaved: $mdPath" -ForegroundColor Magenta
}

# ---------------------------------------------------------------------------
function Invoke-Battery {
    Add-Result "env.hardware" "INFO" "$env:COMPUTERNAME / $((Get-CimInstance Win32_OperatingSystem).Caption)"

    # 1. Silent install (download + extract + initdb + start + connect)
    try {
        & (Join-Path $PSScriptRoot "Get-Postgres.ps1") | Out-Null
        Add-Result "silent.extract" "PASS" "binaries $PgVersion ready"
    } catch { Add-Result "silent.extract" "FAIL" $_.Exception.Message; return }

    $inst = Get-InstanceDir $Name
    if (Test-Path $inst) {
        try { & (Join-Path $PSScriptRoot "Stop-Instance.ps1") -Name $Name -Immediate 2>&1 | Out-Null } catch {}
        Remove-Item -Recurse -Force -Confirm:$false $inst
    }
    try {
        & (Join-Path $PSScriptRoot "New-Instance.ps1") -Name $Name -Port $Port | Out-Null
        & (Join-Path $PSScriptRoot "Start-Instance.ps1") -Name $Name | Out-Null
        Add-Result "silent.initdb_start" "PASS" "private instance on port $Port, no prompts"
    } catch { Add-Result "silent.initdb_start" "FAIL" $_.Exception.Message; return }

    # 2. Write loop + verify
    $w = Invoke-Harness "write_loop.py" "--port $Port --duration $WriteSeconds"
    $written = ([regex]::Match($w.Output, "committed (\d+) rows")).Groups[1].Value
    $v = Invoke-Harness "verify.py" "--port $Port"
    if ($v.ExitCode -eq 0) { Add-Result "integrity.write_verify" "PASS" "$written rows, 0 corrupt" }
    else { Add-Result "integrity.write_verify" "FAIL" $v.Output }

    # 3. Crash-adjacent kill under load + WAL recovery
    $py = Get-VenvPython
    $bg = Start-Process -FilePath $py -PassThru -WindowStyle Hidden `
        -ArgumentList "$(Join-Path $SpikeRoot 'harness\write_loop.py') --port $Port"
    Start-Sleep -Seconds 4
    try { & (Join-Path $PSScriptRoot "Stop-Instance.ps1") -Name $Name -Immediate | Out-Null } catch {}
    if (-not $bg.HasExited) { Stop-Process -Id $bg.Id -Force -Confirm:$false }
    try {
        & (Join-Path $PSScriptRoot "Start-Instance.ps1") -Name $Name | Out-Null
        $log = Get-Content (Join-Path $inst "server.log") -Raw
        $recovered = $log -match "automatic recovery in progress"
        $v2 = Invoke-Harness "verify.py" "--port $Port --expect-min $written"
        if ($v2.ExitCode -eq 0 -and $recovered) {
            Add-Result "crash.wal_recovery" "PASS" "recovery confirmed; $([regex]::Match($v2.Output,'(\d+) rows').Groups[1].Value) rows, 0 corrupt, 0 acked lost"
        } else { Add-Result "crash.wal_recovery" "FAIL" "$($v2.Output); recovered=$recovered" }
    } catch { Add-Result "crash.wal_recovery" "FAIL" $_.Exception.Message }

    # 4. Restore drill. *>&1 captures Write-Host (information stream) too - the
    # success marker lives there; 2>&1 alone would miss it and false-FAIL.
    try {
        $drill = & (Join-Path $PSScriptRoot "Invoke-RestoreDrill.ps1") -SourceName $Name -SourcePort $Port *>&1 | Out-String
        if ($drill -match "restore drill passed") { Add-Result "restore.drill" "PASS" "dump->fresh->restore->verify OK" }
        else { Add-Result "restore.drill" "FAIL" (($drill -split "`n" | Where-Object { $_ -match "verify|FAIL|Error|corrupt" } | Select-Object -Last 2) -join " ") }
    } catch { Add-Result "restore.drill" "FAIL" $_.Exception.Message }

    # 5-8. Items this script cannot prove from inside the guest
    Add-Result "silent.uninstall_keeps_data" "MANUAL" "run installer uninstall; confirm ProgramData\ServiceFlow\data survives"
    Add-Result "powerloss.hard_10x" "MANUAL" "use -Mode PrepPowerLoss / VerifyPowerLoss, 10 cycles from hypervisor"
    Add-Result "service.reboot_survival" "MANUAL" "use -Mode PrepReboot / VerifyReboot (elevated)"
    Add-Result "minor_upgrade" "MANUAL" "run -Mode MinorUpgrade"
    Add-Result "windows_update_reboot" "MANUAL" "trigger WU reboot, then VerifyReboot"
    Add-Result "defender_realtime" "MANUAL" "enable Defender + planned exclusions; re-run Battery, compare write rate"
    Add-Result "disk_full" "MANUAL" "fill disk during writes; expect red health + clean recovery after freeing"
    Add-Result "sleep_wake" "MANUAL" "sleep/resume; confirm app reconnects"

    try { & (Join-Path $PSScriptRoot "Stop-Instance.ps1") -Name $Name | Out-Null } catch {}
}

function Invoke-MinorUpgrade {
    # Real minor bump 16.10 -> target, same data dir, no initdb (checklist item).
    $oldVer = "16.10-1"
    $oldHome = Join-Path $WorkDir "pgsql-$oldVer"
    $oldBin = Join-Path $oldHome "bin"
    if (-not (Test-Path $oldBin)) {
        $zip = Join-Path $WorkDir "postgresql-$oldVer.zip"
        if (-not (Test-Path $zip)) {
            (New-Object System.Net.WebClient).DownloadFile(
                "https://get.enterprisedb.com/postgresql/postgresql-$oldVer-windows-x64-binaries.zip", $zip)
        }
        Expand-Archive -Path $zip -DestinationPath (Join-Path $WorkDir "extract-old") -Force
        Move-Item (Join-Path $WorkDir "extract-old\pgsql") $oldHome -Force
    }
    $uName = "upgrade-src"; $uPort = 5605
    $uData = Get-InstanceDir $uName
    if (Test-Path $uData) { Remove-Item -Recurse -Force -Confirm:$false $uData }

    $pwFile = Join-Path $WorkDir "$uName.pw"; Set-Content $pwFile "spike-only-password" -Encoding ascii -NoNewline
    & (Join-Path $oldBin "initdb.exe") -D $uData -U serviceflow -A scram-sha-256 --pwfile $pwFile -E UTF8 --locale=C --data-checksums | Out-Null
    Add-Content (Join-Path $uData "postgresql.conf") -Encoding ascii -Value "`nport = $uPort`nlisten_addresses='localhost'`ntimezone='UTC'"
    Invoke-PgCtlStart -BinDir $oldBin -DataDir $uData    # isolated start (no pipe-inherit hang)
    Add-Result "minor_upgrade.old_version" "INFO" "initialized on $oldVer"

    $w = Invoke-Harness "write_loop.py" "--port $uPort --duration 8"
    $written = ([regex]::Match($w.Output, "committed (\d+) rows")).Groups[1].Value
    & (Join-Path $oldBin "pg_ctl.exe") -D $uData -m fast -w stop | Out-Null

    # Swap binaries: start the SAME data dir with the new version's pg_ctl, no initdb.
    & (Join-Path $PSScriptRoot "Get-Postgres.ps1") | Out-Null   # ensures $PgBin (target) present
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    Invoke-PgCtlStart -BinDir $PgBin -DataDir $uData
    $sw.Stop()
    # verify.py proves the data survived the binary swap; that IS the upgrade test.
    # (No psql version probe - native-stderr warnings become terminating errors
    # under redirection in PS 5.1, and the versions are already known.)
    $v = Invoke-Harness "verify.py" "--port $uPort --expect-min $written"
    if ($v.ExitCode -eq 0) {
        Add-Result "minor_upgrade" "PASS" "$oldVer -> $PgVersion, no initdb, $written rows intact, downtime $([math]::Round($sw.Elapsed.TotalSeconds,1))s"
    } else { Add-Result "minor_upgrade" "FAIL" $v.Output }
    & (Join-Path $PgBin "pg_ctl.exe") -D $uData -m fast -w stop | Out-Null
}

function Save-Marker($obj) { $obj | ConvertTo-Json | Set-Content $MarkerFile -Encoding utf8 }
function Read-Marker { if (Test-Path $MarkerFile) { Get-Content $MarkerFile -Raw | ConvertFrom-Json } }

function Invoke-PrepPowerLoss {
    & (Join-Path $PSScriptRoot "Get-Postgres.ps1") | Out-Null
    $inst = Get-InstanceDir $Name
    if (-not (Test-Path $inst)) {
        & (Join-Path $PSScriptRoot "New-Instance.ps1") -Name $Name -Port $Port | Out-Null
    }
    & (Join-Path $PSScriptRoot "Start-Instance.ps1") -Name $Name | Out-Null
    $py = Get-VenvPython
    Start-Process -FilePath $py -WindowStyle Hidden `
        -ArgumentList "$(Join-Path $SpikeRoot 'harness\write_loop.py') --port $Port"
    $m = Read-Marker; $cycle = if ($m) { [int]$m.cycle } else { 0 }
    Save-Marker @{ mode = "powerloss"; cycle = $cycle; port = $Port; name = $Name }
    Add-Result "powerloss.prep" "INFO" "writer running, cycle $cycle. NOW hard power-off the VM from the hypervisor, boot, then run -Mode VerifyPowerLoss"
}

function Invoke-VerifyPowerLoss {
    $m = Read-Marker
    if (-not $m -or $m.mode -ne "powerloss") { Add-Result "powerloss.verify" "FAIL" "no prep marker; run PrepPowerLoss first"; return }
    & (Join-Path $PSScriptRoot "Start-Instance.ps1") -Name $m.name | Out-Null
    $inst = Get-InstanceDir $m.name
    $recovered = (Get-Content (Join-Path $inst "server.log") -Raw) -match "automatic recovery in progress"
    $v = Invoke-Harness "verify.py" "--port $($m.port)"
    $cycle = [int]$m.cycle + 1
    Save-Marker @{ mode = "powerloss"; cycle = $cycle; port = $m.port; name = $m.name }
    if ($v.ExitCode -eq 0 -and $recovered) {
        $verdict = if ($cycle -ge 10) { "PASS" } else { "INFO" }
        Add-Result "powerloss.cycle_$cycle" $verdict "recovery ok, 0 corrupt ($cycle/10). $(if($cycle -lt 10){'Run PrepPowerLoss again for next cycle.'}else{'10/10 complete.'})"
    } else { Add-Result "powerloss.cycle_$cycle" "FAIL" "$($v.Output); recovered=$recovered" }
    & (Join-Path $PSScriptRoot "Stop-Instance.ps1") -Name $m.name | Out-Null
}

function Assert-Elevated {
    $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "This mode needs an elevated (Administrator) PowerShell."
    }
}

function Invoke-PrepReboot {
    Assert-Elevated
    & (Join-Path $PSScriptRoot "Get-Postgres.ps1") | Out-Null
    $inst = Get-InstanceDir $Name
    if (-not (Test-Path $inst)) { & (Join-Path $PSScriptRoot "New-Instance.ps1") -Name $Name -Port $Port | Out-Null }
    & (Join-Path $PSScriptRoot "Register-Service.ps1") -Name $Name | Out-Null
    Save-Marker @{ mode = "reboot"; port = $Port; name = $Name; svc = "ServiceFlow-PG-$Name" }
    Add-Result "service.reboot_prep" "INFO" "service registered (auto-start). NOW reboot the VM, then run -Mode VerifyReboot"
}

function Invoke-VerifyReboot {
    $m = Read-Marker
    if (-not $m -or $m.mode -ne "reboot") { Add-Result "service.reboot_survival" "FAIL" "no prep marker; run PrepReboot first"; return }
    $svc = Get-Service $m.svc -ErrorAction SilentlyContinue
    $auto = (Get-CimInstance Win32_Service -Filter "Name='$($m.svc)'").StartMode
    $v = Invoke-Harness "verify.py" "--port $($m.port)"
    if ($svc.Status -eq "Running" -and $auto -eq "Auto" -and $v.ExitCode -eq 0) {
        Add-Result "service.reboot_survival" "PASS" "service auto-started after reboot, data intact"
    } else {
        Add-Result "service.reboot_survival" "FAIL" "status=$($svc.Status) start=$auto verify=$($v.ExitCode)"
    }
}

# --- dispatch ---
switch ($Mode) {
    "Battery" { Invoke-Battery }
    "MinorUpgrade" { Invoke-MinorUpgrade }
    "PrepPowerLoss" { Invoke-PrepPowerLoss }
    "VerifyPowerLoss" { Invoke-VerifyPowerLoss }
    "PrepReboot" { Invoke-PrepReboot }
    "VerifyReboot" { Invoke-VerifyReboot }
}
Write-Report
