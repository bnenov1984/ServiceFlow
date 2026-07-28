# 11 — Security & Data Protection Model

Status: **Approved 10.07.2026; ⚠ amended 11.07.2026 by the web-first pivot (doc
14): the threat model below is written for a LAN app and must be rewritten for an
internet-facing multi-tenant SaaS before Етап 3 exposes a public host** (new top
threats: cross-tenant access → ADR-016; credential stuffing/brute force; public
attack surface; billing webhooks). §2, §3 and §6 remain valid as written; §1's
likelihood table and §7 are stale. The rewrite is an Етап-3 entry task in plan
v3.0. **§2 amended 26.07.2026** with the audit-driven vendor/tenant role
separation target **and the metadata-first vendor visibility rule**
(documentation only — see
[business-os/18](business-os/18_VENDOR_TENANT_ADMINISTRATION.md)); §7's "vendor
cloud" (license API/update feed) describes the **parked local edition**, not
the SaaS Vendor Control Plane above — the two are different concepts sharing
the word "vendor," disambiguated so the Étап-3 rewrite doesn't merge them by
accident. **§1 and §7a amended 28.07.2026** (docs/business-os/18 §9 phase 8,
security/audit hardening): the Vendor Control Plane itself is no longer
prospective — its own threat surface is added to §1's table and detailed in
the new §7a, both scoped strictly to what phase 8 verified is actually built.
The wider Étап-3 rewrite of §1's likelihood table and §7 for the rest of the
public-facing SaaS surface (credential stuffing, billing webhooks, etc.)
remains outstanding, unchanged by this addition. · Date: 10.07.2026 · Basis:
ADR-008/016/017/018, blueprint Part 6

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
| Vendor administrator credential compromise (28.07.2026, §7a) | Med | argon2id hashing, rate-limited login with lockout, DB-backed session distinct from any tenant session, CSRF on every mutation, every login/login_failed/logout audited |
| Cross-tenant access via the Vendor Control Plane (28.07.2026, §7a) | Low | Structural, not just tested: `platform_admin` cannot import any tenant module at the source level (import-linter); a vendor session never binds a `TenantContext` or the RLS GUC, so RLS returns zero rows even under a hypothetical coding mistake |

## 2. Authentication & authorization

Per ADR-008: argon2id password hashes (portable, C5) · DB-backed sessions, HttpOnly
SameSite=Lax cookies · CSRF token on mutations · PIN re-identification scoped to
already-authenticated devices only (never remote login) · idle window → PIN prompt ·
rate limiting on login and PIN attempts (lockout with Owner unlock). Authorization:
one Owner boolean checked at the API layer (08 §identity); the permission matrix is
02 §12 verbatim. Every mutation records the acting user (BR-5).

**Vendor/tenant role separation (added 26.07.2026, audit-driven — full model in
[business-os/18_VENDOR_TENANT_ADMINISTRATION.md](business-os/18_VENDOR_TENANT_ADMINISTRATION.md),
ADR-BOS-009/010):** today exactly one role bit exists (`is_owner`), scoped to
one tenant; no vendor/platform-admin identity exists in code. The target model
— not yet built — keeps a Vendor Administrator identity (a new, `company_id`-
less table, its own session kind) permanently structurally separate from
`users`/`is_owner`: no boolean-on-`users` shortcut, no shared session type,
no implicit cross-tenant read. Vendor Control Plane routes will require their
own `require_platform_admin` dependency, satisfiable only by a vendor session,
and every vendor mutation will be audited (actor, target company, action,
reason, timestamp) in a Core-owned log distinct from the tenant `audit_log`.
This paragraph documents the target for the Étап-3 rewrite below to build
against; it does not itself change current behavior.

**Vendor data visibility — metadata-first, not tenant-business-data-first
(PO clarification, 26.07.2026 — ADR-BOS-009 §Vendor data visibility).** A
vendor administrator administers *companies as customers*, not *companies'
businesses*. Visible by default: company identity, subscription/licence
status, activated applications, seat limit and usage, RepairFlow business
profile, suspension status, deployment/version/health metadata, internal
support notes, platform audit history. **Not** visible: customers, assets,
service orders, engagements, documents, invoices and tenant transactions,
and notes belonging to the customer company — aggregate counts over these
are metadata and stay visible, individual rows do not. This matters for the
threat model specifically because the prohibited set is where the tenant's
*own customers'* personal data lives, including device passcodes (§5), for
which the tenant — not the vendor — is the GDPR controller (§6). Mechanically
the default is already fail-closed: a vendor session produces no
`TenantContext`, so RLS's unset-GUC policy (ADR-016) returns zero rows; the
Control Plane must be built never to need an RLS exemption rather than being
granted one for convenience. Any future support access to tenant operational
data must be separately designed, explicitly authorised, time-bounded where
practical, and strongly audited per accessed record — out of scope for the V1
Vendor Console, as is vendor impersonation.

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

## 7a. Vendor Control Plane threat surface (SaaS, built — 28.07.2026)

Not the same "vendor" as §7 above (see the status line's disambiguation). This
section covers the Vendor Control Plane docs/business-os/18 phases 1–7
actually built, verified in phase 8's hardening pass — not the rest of the
Étап-3 SaaS surface, which stays outstanding.

- **Vendor credential compromise**: same discipline as tenant auth (ADR-008)
  — argon2id, rate-limited login with lockout, DB-backed session, CSRF on
  every mutation. A vendor session is structurally a different kind from a
  tenant session (its own table, its own cookie, no `company_id` anywhere on
  it — `test_platform_admin_has_no_company_id`) and cannot be forged from a
  tenant token or vice versa (`test_a_vendor_session_token_is_not_a_tenant_
  session_token`, `test_tenant_user_cannot_authenticate_as_vendor_admin`).
- **Cross-tenant access via a Vendor Control Plane bug**: prevented at the
  source level, not only by runtime testing — `backend/.importlinter`'s
  `vendor-plane-not-tenant-code` contract forbids `business_os.platform_admin`
  from importing any tenant module (every `serviceflow.*` vertical,
  `professional_services`, and `business_os.identity.deps`) at all, so a
  query against a tenant table cannot even be written inside the vendor
  plane's own code. Backed by two runtime proofs over the *entire* mounted
  route graph, not one hand-picked endpoint: `test_vendor_request_never_sets_
  the_tenant_rls_guc` (no vendor request ever binds the RLS GUC, so even a
  hypothetical slip returns zero rows) and `test_every_vendor_route_touches_
  no_tenant_table` (every vendor route — login, reads, provisioning,
  entitlement grant/revoke, subscription transition — invoked for real and
  checked against every tenant operational table).
- **Unaudited vendor mutation**: `platform_audit_log` is the only write path
  (`platform_admin.audit.record`, unreachable from tenant code by the same
  import-linter contract, append-only at the database level via trigger
  regardless of role). Completeness — every state-changing vendor route
  actually writes a row — is proved structurally over the route graph
  (`test_every_vendor_mutation_route_writes_an_audit_record`), the same
  discipline `test_every_csrf_route_outside_identity_also_requires_
  subscription_ok` established for the subscription retrofit, not by trusting
  that each new route remembers to add its own audit call.
- **Vendor support impersonation**: not implemented, explicitly out of scope
  for V1 (ADR-BOS-009) — flagged here, not solved here.
- **Stronger auth for sensitive vendor actions** (suspend, entitlement
  revoke): open question, same as docs/business-os/18 §1.8 — not blocking V1,
  should be resolved before real paying customers depend on it.

## 8. What we deliberately do not build (and why)

No 2FA in V1 (LAN app, PIN model; SaaS revisits) · no field-level encryption beyond
§5 (DB file lives on the shop's own machine — disk encryption is Windows guidance,
not app scope) · no WAF/IDS (no exposed internet surface) · no SOC2-style controls
(single developer, no cloud multi-tenancy yet — SaaS edition will revisit honestly).
