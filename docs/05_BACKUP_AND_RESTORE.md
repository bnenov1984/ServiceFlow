# 05 — Backup, Verification & Restore (A7)

Status: **Approved by Product Owner 10.07.2026** · Date: 10.07.2026
Design document — no implementation.
Principle (PO directive #5): **a backup that has not been proven restorable does not
count as a backup.** The system never reports "backed up" — it reports "restorable".

---

## 1. The artifact

One versioned archive = the single format serving three obligations (ADR-012):
nightly backup, GDPR company export, and the future Local→SaaS migration payload.

Contents: full database dump · attachment files (content-addressed, physically
incremental — unchanged photos are referenced, not recopied; the artifact is always
*logically* complete) · configuration & license state · manifest (app version, schema
version, entity counts, per-file checksums, created-at, artifact format version).

## 2. Schedule & retention

- **Nightly** full logical backup (default 03:00, configurable), plus **automatic
  pre-update backup** (04 §2) and **Owner-triggered "Бекъп сега"** (tray/settings).
- Retention (configurable, GFS defaults): 7 daily · 4 weekly · 12 monthly. Disk-space
  projections surfaced in health; oldest pruned only after successor verification.

## 3. Destinations

1. **Primary:** local backup directory (always).
2. **Secondary (strongly pushed in onboarding):** USB drive, network share, or a
   cloud-synced folder (Drive/Dropbox/OneDrive — the shop's choice; sync happens
   outside our product).
   Health turns **yellow** when the secondary hasn't received a verified artifact
   for > 3 days, with plain-Bulgarian instructions („Включете USB диска…").
   Ransomware note in onboarding: a periodically disconnected USB copy is the shop's
   cheapest real protection; the product reminds, never nags silently.

## 4. Verification — the part that makes it real

**Nightly restore rehearsal (full):** after each backup, a job restores the dump into
a scratch database (same bundled instance, isolated DB), then asserts:
- schema version matches the artifact manifest;
- entity counts match manifest counts;
- referential spot checks (every order → existing customer/asset; every payment →
  existing order);
- domain invariants: invoice number sequence gapless per company · exactly one
  terminal outcome per terminal order · derived totals recompute to stored manifest
  totals;
- file sample check: random N attachments' checksums verified against manifest
  (full file sweep weekly).

**Fast verify (pre-update path, 04):** dump integrity + schema + counts only, to keep
update downtime short.

**Result = health state:** green „Последен бекъп: възстановим (вчера 03:12)" ·
red = failed verification → tray alert, dashboard banner for Owner, and (if opted in)
vendor diagnostics signal. The scratch DB is dropped after each rehearsal; the
rehearsal also doubles as the migration-rehearsal target during updates (04 §2).

## 5. Restore

**Wizard (Owner or remote-guided):**
choose artifact (list shows date, version, counts, verification history) → checksum
validation → explicit confirmation showing what will be replaced → maintenance mode →
safety snapshot of current state (even a broken state is preserved before restore) →
restore DB + files + config → migrations if artifact is older than installed app →
health suite → report („Възстановени: 4 812 поръчки, 1 093 клиента…").

Version rules: artifact **older** than app → restore, then migrate forward (the
rehearsed path). Artifact **newer** than app → refuse with guidance („Първо обновете
приложението") — never a half-understood restore.

**Bare-metal path (dead PC):** new Windows PC → run installer → „Възстановяване от
бекъп" entry point → point at USB/cloud folder artifact → same wizard → license
re-activation (license API accepts hardware change; flagged in vendor console).
**Target: shop operational in < 1 hour** from unboxing, assuming artifact exists.

## 6. Failure scenarios

| Scenario | Design answer |
|---|---|
| Backup fails (disk full, DB down) | Red health immediately, retry with backoff; never silently skipped; 2 consecutive failures → prominent Owner alert |
| Verification fails but backup "succeeded" | Treated identically to backup failure — the artifact is marked unusable and excluded from retention counting |
| Corrupted artifact at restore time | Checksums fail fast; wizard offers next-newest verified artifact |
| Restore fails midway | Pre-restore safety snapshot is restored; nothing is worse than before the attempt |
| Clock skew / DST | All artifacts keyed by UTC + monotonic sequence, displayed in local time |
| Shop deletes backup folder | Health yellow/red on missing primary; secondary still holds copies |

## 7. Acceptance criteria (release gate)

1. Restore drill from each retention tier (daily/weekly/monthly) succeeds unattended.
2. Bare-metal drill on a clean machine meets the < 1 hour target.
3. A deliberately corrupted artifact is detected before any destructive step.
4. Verification failure is visible to the Owner within one minute of occurrence.
5. Time-to-restore for a reference dataset (5 k orders, 20 GB photos) ≤ 15 minutes
   excluding file copy from slow media.
