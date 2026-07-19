# PS-20 — Roles and Permissions

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

## 1. Fixed roles, not capability grids (commissioned evaluation)

Platform reality: Core has exactly one permission concept — the `is_owner`
boolean (BOS-02 rejected RBAC platform-wide; "the first module that needs
finer grants pays for it"). This module is that first module, and it pays
with the **smallest sufficient step**: one module-role enum per user, fixed
matrix in code.

Capability-based permissions were evaluated and rejected for v1: a 3–15
person firm cannot administer 14 toggles per user (Мария would not); fixed
roles are explainable in one sentence each; the matrix below is code —
testable, documented, and cheap to extend *if* a real firm outgrows it
(recorded trigger in [34]). Per-assignment confidentiality walls: same
verdict, same trigger ([02] §3).

## 2. Roles

`ps_member_roles`: (company_id, user_id, role ∈ `manager | worker |
readonly`). Core `is_owner` ⇒ superset of manager plus owner-only rights.
A Core user with no row has no module access (module activation ≠ access
for everyone). Assigning roles: owner/manager (FR-PS-110).

| Role | Persona | One-sentence meaning |
|---|---|---|
| owner (Core) | Мария as principal | everything, including settings, users, terminal-revert, audit trail |
| manager | Мария day-to-day, senior colleague | run all work: full assignment control, deadlines, cancel, clients, config of catalog items |
| worker | Георги, Иванка | do the work: create/edit assignments, actions, tasks, files, communications; no cancel, no official-deadline changes, no config |
| readonly | П-5 accountant | see, never touch; financial columns per §4 |

## 3. Permission matrix (server-enforced, FR-PS-111)

| Capability | owner | manager | worker | readonly |
|---|---|---|---|---|
| view all assignments | ✔ | ✔ | ✔ (MVP transparency default) | ✔ |
| create assignment / edit fields | ✔ | ✔ | ✔ | — |
| stage transitions, next actions, tasks, files, communications, requirements | ✔ | ✔ | ✔ | — |
| change internal target | ✔ | ✔ | ✔ (own assignments) | — |
| change official deadline (reason req.) | ✔ | ✔ | — | — |
| deliver / complete | ✔ | ✔ | ✔ own assignments | — |
| cancel | ✔ | ✔ | — | — |
| revert terminal ≤24 h ([11] §3) | ✔ | — | — | — |
| manage clients | ✔ | ✔ | create/edit (no deactivation) | — |
| view money ([21]) | ✔ | ✔ | org toggle (default off) | org toggle per user (accountant on) |
| edit money entries | ✔ | ✔ | — | — |
| manage service types / workflows / checklist templates | ✔ | ✔ | — | — |
| org settings (labels, thresholds, holidays) | ✔ | ✔ | — | — |
| manage users' module roles | ✔ | ✔ (not owners) | — | — |
| view assignment activity & deadline history | ✔ | ✔ | ✔ | ✔ |
| view admin audit trail | ✔ | — | — | — |

Workers see all assignments by default (small-firm transparency; Стоян's
solo case trivially so). "Workers see only assigned" is a deferred org
toggle — the schema needs nothing for it now.

## 4. Auditability hooks (commissioned requirement)

Deadline changes ([13] §5), lifecycle transitions ([11] §2), terminal
reverts, role changes, money edits, and soft deletions all write activity/
audit events with actor and reason where applicable. The split between
business activity events and the platform audit log is defined in
[30_SECURITY_PRIVACY_AND_AUDIT.md](30_SECURITY_PRIVACY_AND_AUDIT.md).

## 5. Enforcement

Every route enforces the matrix server-side (NFR-PS-10) via one module
dependency (`require_ps_role(...)`) layered on Core's session dependencies
(`identity.deps`) — UI hiding is convenience. Permission tests enumerate
the matrix ([32] §T-6); the matrix table above is the normative source.
