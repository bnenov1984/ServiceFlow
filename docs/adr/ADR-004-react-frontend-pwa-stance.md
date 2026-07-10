# ADR-004 — React/TypeScript Frontend & PWA Stance

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §D4, PO directive #1, OQ-A2

## Context
The UI must serve low-digital-confidence Bulgarian users on desktop, tablet and phone
over LAN; Kanban drag-and-drop with optimistic updates is the primary surface; the
identical frontend must serve the SaaS edition. PO directive: keep PWA, no offline
data sync. Browser constraint: full PWA installation requires a secure context —
`localhost` qualifies, plain `http://LAN-IP` does not.

## Decision
React 18+ + TypeScript + Vite + Tailwind CSS + TanStack Query, served by the local
application as an SPA with a web app manifest. PWA scope in V1: installable shell on
the server machine (localhost), manifest + responsive web app everywhere else. No
service-worker offline data features. LAN HTTPS provisioning (enabling full PWA on
client devices) deferred to V1.5 (OQ-A2, approved).

## Alternatives considered
- **Vue 3 + TS** — comparable capability, smaller local talent pool, no decisive
  advantage. Rejected.
- **Server-rendered (Jinja/HTMX)** — least JavaScript, but fights drag-and-drop,
  optimistic UI and the SaaS reuse story. Rejected.

## Consequences
- **Advantages:** typed API client generated from backend contracts; mature DnD and
  form ecosystems; one frontend for both editions.
- **Disadvantages:** SPA weight demands discipline (bundle budget, loading states);
  React offers many wrong ways to stay simple.
- **Risks:** UI complexity creep violating the "understandable in minutes" promise.
  Mitigation: UI/UX specification (blueprint stage) is normative; screens beyond the
  core four require PO approval.

## Reconsideration triggers
V1.5 LAN HTTPS work revisits the PWA scope; a native mobile requirement (explicitly
out of scope) would trigger its own ADR, not amend this one.
