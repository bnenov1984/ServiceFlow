# Installer Walking Skeleton (Stage 0 deliverable, ADR-005)

Goal of the skeleton: prove the shape, not polish — one signed installer that
produces a working two-service install with a tray showing **real** health.

## Composition (planned)
- **Inno Setup** script (pragmatic choice: free, battle-tested, scriptable; WiX is
  the enterprise pattern we skip until something concrete demands MSI).
- Services: ServiceFlow app (bundled embedded Python runtime) + bundled PostgreSQL
  (per the spike setup) — both via `pg_ctl register` / WinSW-managed service wrapper.
- Tray app: minimal (health dot polling `/api/v1/platform/health`, "Отвори
  приложението" → default browser at localhost, "Изход" only stops the tray).
- Firewall rule for LAN access; mDNS registration (`serviceflow.local`, OQ-A5)
  arrives Stage 6 with the rest of platform.

## Skeleton acceptance (Stage 0)
- [ ] One .exe installer → next/next/finish on a clean VM → browser opens the app
      shell showing health from the real backend.
- [ ] Both services survive reboot.
- [ ] Uninstall is clean (data dir preserved with a clear folder name).
- [ ] Build is reproducible in CI (unsigned artifact) — **code-signing certificate
      procurement is a business task for the PO now** (EV/OV cert, weeks of lead
      time; unsigned builds trip SmartScreen and AV heuristics).

## Deferred to Stage 6 (per 13)
Auto-update pipeline (04), backup destinations UX (05), license activation
(ADR-009), support package, "Възстановяване от бекъп" installer entry (05 §5).
