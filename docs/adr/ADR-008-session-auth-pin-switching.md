# ADR-008 — Server-Side Sessions + PIN Fast-Switching

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §D8

## Context
A LAN web app with 1–20 users, often sharing one counter PC. The timeline's
trustworthiness (01 §BR-5) depends on every action being attributable to the right
person, yet full logout/login per interaction would be abandoned within a day.

## Decision
Server-side sessions in the database, HttpOnly cookies (SameSite=Lax), CSRF
protection on mutations, passwords hashed with argon2id (portable per migration
constraint C5). **PIN fast-switching:** each device authenticates once per day with
full credentials; thereafter, users re-identify per action window with a short
personal PIN; the active identity is always visible on screen; switch events are
logged. Idle windows revert to the PIN prompt.

## Alternatives considered
- **JWT bearer tokens** — solves distribution problems a LAN app doesn't have;
  localStorage XSS surface; revocation complexity. Rejected (blueprint's own
  challenge: "evaluate whether JWT is truly best" — it is not, here).
- **Windows-integrated auth** — assumes domain-joined machines small shops don't
  have. Rejected.
- **Shared shop account (no identity)** — destroys attribution and BR-5. Rejected.

## Consequences
- **Advantages:** simple, revocable, browser-native; truthful "who" at counter
  speed; hashes and sessions carry into SaaS unchanged.
- **Disadvantages:** PIN UX is custom engineering; PINs are weaker secrets — scoped
  only to re-identification on an already-authenticated device, never remote login.
- **Risks:** PIN sharing between colleagues. Mitigation: visible identity, switch
  logging, owner-visible audit; cultural, not purely technical.

## Reconsideration triggers
SaaS edition may add an IdP/SSO layer for large customers — additive, sessions
remain the base mechanism.
