# PS-30 — Security, Privacy and Audit

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Inherits the platform security model (docs/11, ADR-016) wholesale; this
document adds only what is module-specific.

## 1. Threat posture (module deltas)

| Asset | Threat | Control |
|---|---|---|
| Assignment data across tenants | cross-tenant leak | ADR-016 full regime (INV-1); isolation tests grow with every `ps_*` migration (P0) |
| Dossier files | unauthorized fetch, guessable keys | storage-port keys unguessable; every download authorised against the assignment's tenant + viewer role (NFR-PS-11) |
| Deadline history | falsification ("the deadline was always the 20th") | INV-10/INV-11 append-only + reasoned-change chokepoint; DB trigger blocks UPDATE/DELETE |
| Money visibility | over-broad exposure inside the firm | server-side response shaping per role ([21] §5) — not UI hiding |
| Personal identifiers (ЕГН) | stored by habit, leaked by export | off-by-default column, org opt-in, manager+ visibility, flagged in export ([16] §4) |
| Free-text fields (titles, notes) | PII accumulation | data-minimisation guidance in UI help; anonymization flow includes guided free-text review ([16] §4); no PII in logs (platform rule) |
| Notifications | information leak via stale params | message params carry ids + minimal facts; money amounts never in params ([21] §5) |

## 2. The three record layers (kept distinct on purpose)

| Layer | Table | Audience | Content | Mutability |
|---|---|---|---|---|
| Business activity | `ps_activity_events` | all module users (S-4 История) | domain happenings: stage changed, file added, call logged | append-only (INV-10) |
| Deadline forensics | `ps_deadline_changes` | all who see the assignment | old/new/reason/actor for the two guarded dates | append-only |
| Platform security audit | Core `audit_log` | Core owner (+ platform admin) | logins, role changes, terminal reverts, anonymization runs, export runs | Core-owned |

Rationale: mixing business history with security audit either over-exposes
security events or under-exposes business history; ServiceFlow's
timeline-vs-AuditLog split proved the pattern (BOS-05 §3) — pattern reused,
tables owned here.

## 3. GDPR summary (details in [16] §4, [17] §5)

- Roles: firm = controller; platform operator = processor (DPA is Етап-3
  platform work — flagged, [28] §3.4).
- Data minimisation: no ЕГН by default; address free-text; communication
  log records facts, not correspondence bodies.
- Subject rights: access/portability via tenant export (ADR-012 section);
  erasure via person-client anonymization preserving business records
  (legitimate-interest retention of engagement facts); rectification =
  normal editing.
- Files: deep-PII carriers; access-controlled, never scanned, retention is
  the firm's professional duty (stated in settings help, not per-upload
  nagging).

## 4. AppSec specifics

- All routes behind Core session + CSRF deps; `require_ps_role` matrix
  ([20] §5); no module-specific auth surface.
- Uploads: size/type limits, content-type not trusted, served with
  download-safe headers; no in-browser rendering of user HTML/SVG.
- JSONB `details` validated against the code-owned schema before persist
  (no schema-less writes; [25] §3).
- Number sequences and dedup keys give no cross-tenant information (scoped
  unique indexes include company_id).

## 5. Audit acceptance (ties to [37])

Auditable-by-design actions — deadline changes, lifecycle transitions,
terminal reverts, role changes, money edits, anonymization, soft deletes —
each demonstrably produce their layer's record in tests ([32] §T-7); a
release in which any of them silently succeeds without its record is
release-blocking.
