; ServiceFlow installer - walking skeleton (Inno Setup 6).
; Stage 0 scope: shape only (ops/installer/README.md). Compile with ISCC.exe.
; Product name comes from config - never hardcode branding beyond this define.
#define ProductName "ServiceFlow"
#define ProductVersion "0.1.0"

[Setup]
AppId={{7E1C9B2A-4A73-4A1B-9C64-SERVICEFLOW1}
AppName={#ProductName}
AppVersion={#ProductVersion}
DefaultDirName={autopf}\{#ProductName}
DisableProgramGroupPage=yes
OutputBaseFilename=serviceflow-setup-{#ProductVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
; SignTool configured once the code-signing certificate arrives (PO task):
; SignTool=standard

[Files]
; Populated by the build pipeline (Stage 6 wires the real payloads):
; - app\        embedded Python runtime + backend + built frontend
; - pgsql\      PostgreSQL binaries (the spike-validated distribution)
; - tray\       tray application
Source: "payload\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Dirs]
; Data lives outside {app} so uninstall/upgrade never touches it (05, ADR-014).
Name: "{commonappdata}\{#ProductName}\data"; Permissions: system-full

[Run]
; Post-install bootstrap (idempotent PowerShell, exit code checked):
; initdb private instance -> register both services -> firewall rule -> start -> health poll
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\bootstrap\Install-Services.ps1"" -DataRoot ""{commonappdata}\{#ProductName}"""; \
  StatusMsg: "Настройване на услугите..."; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\bootstrap\Remove-Services.ps1"""; \
  RunOnceId: "RemoveServices"; Flags: runhidden waituntilterminated
; Uninstall preserves {commonappdata}\ServiceFlow\data by design (checklist item).
