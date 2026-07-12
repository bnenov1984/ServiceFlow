# 11 — Security & Data Protection Model

Status: **Approved 10.07.2026; ⚠ amended 11.07.2026 by the web-first pivot (doc
14): the threat model below is written for a LAN app and must be rewritten for an
internet-facing multi-tenant SaaS before Етап 3 exposes a public host** (new top
threats: cross-tenant access → ADR-016; credential stuffing/brute force; public
attack surface; billing webhooks). §2, §3 and §6 remain valid as written; §1's
likelihood table and §7 are stale. The rewrite is an Етап-3 entry task in plan
v3.0. · Date: 10.07.2026 · Basis: ADR-008/016/017/018, blueprint Part 6

## 1. Threat model (what we actually defend against)

| Threat | Likelihood | Primary control |
|---|---|---|
| Misuse on shared counter PC (wrong/fake identity) | High | PIN switching + visible identity + switch logging (ADR-008) |
| Stolen/lost backup media (USB with the whole business) | High | Optional artifact encryption (§4) + onboarding guidance |
| Curious LAN guest (customer wifi reaching the server) | Medium | Auth on every request; no anonymous endpoints; firewall rules scoped by installer; guidance to keep server off guest wifi |
| XSS via user content (names, notes, complaints) | Medium | Framework auto-escaping; CSP; no HTML in user content |
| Dependency vulnerabilities | Medium | Locked deps, automated advisories, PATCH release channel (04) |
| Ransomware on shop PC | Medium | Offline USB backup practice (05 §3); product survives via bare-metal restore |
| License tampering (clock rollback, token copy) | Low-Med | Signed tokens, monotonic checks (ADR-009); accepted as not-an-arms-race |
| Targeted network attack on a repair shop | Low | Standard hardening only — this is not a bank; effort goes where likelihood is |

## 2. Authentication & authorization

Per ADR-008: argon2id password hashes (portable, C5) · DB-backed sessions, HttpOnly
SameSite=Lax cookies · CSRF token on mutations · PIN re-identification scoped to
already-authenticated devices only (never remote login) · idle window → PIN prompt ·
rate limiting on login and PIN attempts (lockout with Owner unlock). Authorization:
one Owner boolean checked at the API layer (08 §identity); the permission matrix is
02 §12 verbatim. Every mutation records the acting user (BR-5).

## 3. Application controls (standard, non-negotiable)

Parameterized queries only (SQLAlchemy) · strict input validation at the API boundary
(Pydantic) · security headers (CSP, X-Content-Type-Options, frame-ancestors 'none') ·
uploads: extension+MIME+magic-bytes check, images re-encoded (kills embedded
payloads and HEIC in one step), served with safe content-disposition through
authorized streams only (ADR-007 — no direct file shares) · no PII in logs (log ids,
not names/phones) · secrets (DB password, license keys, encryption key) in a
machine-local config protected by filesystem ACLs, generated at install, never in
source control.

## 4. Backup artifact protection

Artifacts contain the entire business. Default: unencrypted locally (a forgotten
passphrase = total data loss for a non-technical owner — the honest trade-off).
**Onboarding strongly recommends encryption when a cloud-synced or portable
secondary destination is configured**; passphrase set by Owner with an unmissable
„няма възстановяване без нея" warning + printed recovery-sheet prompt. Encryption
covers the whole artifact (05 format), verified by the nightly rehearsal like any
other artifact.

## 5. Sensitive asset fields (device passcodes — BR-10 resolved)

Included in V1 (shops genuinely need customer passcodes to test repairs): stored
app-level encrypted (08 §assets.sensitive_values), never in search/exports' plain
sections, masked in UI, „Покажи" reveals for 30 s and writes an audit_log entry.
GDPR export includes them encrypted; anonymization erases them.

## 6. GDPR (technical readiness — legal review stays a launch gate)

The shop is the data controller; the product makes compliance mechanically possible:
- **Anonymize customer** (Owner, two-step): personal fields overwritten („Изтрит
  клиент"), passcodes erased, orders/invoices/history retained (legal + operational
  legitimacy), irreversible, audited.
- **Export**: per-customer data extract; whole-company export = the standard artifact
  (ADR-012).
- **Retention**: orders kept indefinitely by default (repair history is the product's
  value); audit_log pruned at 24 months (OQ-DB1); configurable retention job exists
  for future policy needs.
- Invoices are **never** anonymized or deleted (legal retention obligations trump
  erasure requests for tax documents — flagged for the accountant/legal review).
- Telemetry (A3): strictly opt-in, crash/diagnostic only, no business data — the
  support package generator strips names/phones/identifiers by construction (03 §4).

## 7. Vendor cloud (the small attack surface we host)

License API + update feed + support inbox (03 §4): TLS only · signed license tokens
and signed release packages (private keys never on shop machines) · vendor console
behind admin auth + audit log (A4) · support packages retained 90 days then purged ·
no shop business data by design. A compromise of the update feed is the worst
realistic scenario → release signing keys kept offline; updater verifies signatures
against a pinned public key baked into the installed app (04 §2 preconditions).

## 8. What we deliberately do not build (and why)

No 2FA in V1 (LAN app, PIN model; SaaS revisits) · no field-level encryption beyond
§5 (DB file lives on the shop's own machine — disk encryption is Windows guidance,
not app scope) · no WAF/IDS (no exposed internet surface) · no SOC2-style controls
(single developer, no cloud multi-tenancy yet — SaaS edition will revisit honestly).
