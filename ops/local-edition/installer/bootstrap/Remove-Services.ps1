# Uninstall hook: remove services, keep data (checklist: uninstall preserves data dir).
$ErrorActionPreference = "SilentlyContinue"
Stop-Service "ServiceFlow-App" -Force
Stop-Service "ServiceFlow-PG" -Force
$AppRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $AppRoot "tray\serviceflow-app-svc.exe") uninstall
& (Join-Path $AppRoot "pgsql\bin\pg_ctl.exe") unregister -N "ServiceFlow-PG"
Remove-NetFirewallRule -DisplayName "ServiceFlow LAN"
# %ProgramData%\ServiceFlow\data is intentionally NOT touched.
exit 0
