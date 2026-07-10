# ADR-005 — Native Windows Installer, Two Services + Tray App

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §D5

## Context
Non-technical shop owners must install, run and survive reboots/power loss without a
technician. The single most common failure mode of local-deploy products is the
machine environment, not the application.

## Decision
A signed native Windows installer that produces: (1) the ServiceFlow service (app +
in-process jobs, auto-start), (2) the bundled private PostgreSQL service (ADR-002),
and (3) a small tray/status app: health dot, "Отвори приложението", "Бекъп сега",
"Пакет за поддръжка". The installer applies antivirus exclusions, firewall rules for
LAN access, and mDNS registration (`serviceflow.local`, per approved OQ-A5:
localhost → serviceflow.local → fallback LAN IP). A "Възстановяване от бекъп" entry
point supports bare-metal recovery (05 §5).

## Alternatives considered
- **Docker Desktop + Compose on shop PCs** — dev/prod parity, but WSL2, licensing,
  virtualization BIOS flags and Docker updates on random shop machines are support
  hell. Rejected for customers; retained for development environments.
- **Electron app embedding everything** — familiar install UX but single-machine
  bias against the multi-user LAN requirement; browser clients needed regardless.
  Rejected.
- **Manual install guide (zip + scripts)** — zero engineering, unlimited support
  cost. Rejected.

## Consequences
- **Advantages:** no prerequisites; reboot-safe; one artifact for the update
  strategy (04); tray gives owners a truthful one-glance status.
- **Disadvantages:** installer/updater is real, ongoing engineering, treated as a
  product module with its own acceptance criteria (04 §6, 05 §7).
- **Risks:** Windows variety (home routers, AV brands, sleep policies). Mitigation:
  reference-hardware matrix in the testing strategy; Stage-0 hardening spike
  (ADR-002 gate covers both).

## Reconsideration triggers
SaaS edition makes local installs a minority channel; installer scope then shrinks
but this ADR still governs the local edition.
