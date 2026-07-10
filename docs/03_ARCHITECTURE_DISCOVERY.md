# 03 — Architecture Discovery

Status: **Approved by Product Owner 10.07.2026.** OQ-A1…A5 all approved as proposed:
A1 30-day offline grace, no lockout, read-only+export after expiry · A2 LAN HTTPS →
V1.5, V1 = responsive local web app · A3 crash telemetry strictly opt-in, no customer
data · A4 minimal Vendor Admin Console (licensing, diagnostics, updates, support
packages, logs) · A5 access order: localhost → serviceflow.local (mDNS) → fallback
LAN IP. Additional discovery requests A6/A7/A8 delivered as documents 04, 05, 06.
Date: 10.07.2026
Input: Blueprint Part 6 + approved 00 (discovery), 01 (domain), 02 (workflow)
Output per Part 6: context analysis, options with trade-offs, recommended
architecture, module boundaries, migration strategy, risks, ADR candidates, open
questions. **No implementation, no database schema, no code.**

---

## 1. Context Analysis (what the architecture must actually carry)

| Dimension | Reality |
|---|---|
| Business complexity | Moderate: CRUD + one status workflow + derived money + immutable documents. No distributed transactions, no heavy computation. |
| Users / concurrency | 1–20 users per installation; realistically 2–6 concurrent; write conflicts rare (per-order work is naturally partitioned). |
| Data volume | Small: a busy shop ≈ 30–60 orders/day → ~15 k orders/year, few hundred customers/month. Photos dominate: ~50–100 GB over 3 years worst case. |
| Deployment | One shop-owned Windows PC as server; browsers on LAN clients; non-technical operators; machine may sleep/reboot/run antivirus. |
| Offline | Daily work must not require internet. Internet needed only for: license refresh, updates, support package upload, (V1.5) SMS/Viber. |
| SaaS future | Same domain core must later run multi-tenant in cloud. Local V1 export must import into SaaS. |
| Backup | MVP feature: automatic, verified-restorable, one-click restore (PO directive #5). |
| Reporting | V1: filtered lists + dashboard counters only. |
| Integrations | None in V1. V1.5+: SMS/Viber, label printers, accounting export. |
| Vendor side | **Subscription licensing makes a minimal vendor cloud part of V1** — see §4 (this is a scope fact, not a choice). |

Conclusion the analysis forces: the risk lives in **operations and packaging**, not
in domain computation. The architecture optimizes for: one artifact to install, one
artifact to back up, one artifact to update, and a domain core with zero knowledge of
where it runs.

## 2. Major Decisions — Options & Trade-offs

Each decision: ≥3 alternatives, recommendation, and the trigger that would reopen it.
Ratings: cost/complexity vs. our context, not in absolute terms.

### D1. Application architecture style

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. Modular monolith** — one deployable, explicit module packages with enforced boundaries | One install/update/backup; boundaries give SaaS-era extraction options; testable per module | Requires discipline (import rules) | **Recommended** |
| B. Layered monolith (controllers/services/repos, no module boundaries) | Slightly less ceremony | "Big ball of mud" by year 3; SaaS extraction painful | Rejected |
| C. Service-split (2+ processes: core, documents, jobs) | Independent scaling | Distributed complexity a 6-person shop will never need; multi-service ops on a shop PC is absurd | Rejected |

Nothing is independently deployable in V1 — including background work (D6).
Reopen trigger: none foreseeable before SaaS scale data exists.

### D2. Database engine

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. PostgreSQL, bundled and fully managed by our installer** (private instance, own port, own data dir, Windows service) | Same engine local & SaaS (removes the riskiest migration variable); JSONB for asset-type fields; pg_trgm for Cyrillic/Latin fuzzy search; serializable/advisory locks for gapless invoice numbering; pg_dump/pg_restore = scriptable verified backups | Heavier ops footprint on a shop PC — a service to babysit; version upgrades are ours to automate | **Recommended** |
| B. SQLite (embedded, WAL mode) | Zero-admin; backup = file copy; adequate concurrency behind a single app process | Engine divergence from SaaS (dual-dialect testing forever or a migration cliff); weaker fuzzy search; gapless numbering and JSON are workable but hand-rolled | Rejected — but **narrowly**; see trigger |
| C. SQL Server Express | Windows-native | 10 GB cap, licensing questions, no SaaS parity, heavier than A | Rejected |

The honest note: SQLite is the better *pure-V1* choice; PostgreSQL is the better
*one-product-two-deployments* choice, and the PO's strategy is explicitly the latter.
**Reopen trigger:** if Stage-0 installer testing shows bundled PostgreSQL cannot be
made invisible to non-technical users (silent install, auto-recovery after power
loss, unattended minor upgrades), switch to SQLite before any schema exists — the
ADR must record this exit ramp and its deadline.

### D3. Backend stack

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. Python 3.12 + FastAPI + SQLAlchemy + Alembic + Pydantic** | Fast domain iteration; first-class validation (Pydantic) and migrations (Alembic); async fits in-process jobs; large BG talent pool; identical codebase serves SaaS later | Windows packaging needs a bundled/embedded Python runtime (installer owns it — solved problem) | **Recommended** |
| B. .NET 8 / C# | Best-in-class Windows deployment (single self-contained exe, first-class services); strong typing | Slower product iteration for a solo/small team unless already .NET-fluent; its main advantage (packaging) we replicate via bundling | Runner-up — viable if the team were .NET-native |
| C. Node.js + TypeScript | One language across stack | Weaker migration/ORM story for this shape of domain; packaging on Windows no better than A | Rejected |

Technology follows the business problem: the problem is domain iteration speed +
SaaS reuse; packaging is a one-time installer problem. Hence A over B.

### D4. Frontend stack

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. React + TypeScript + Vite + Tailwind + TanStack Query** | Mature drag-and-drop and PWA tooling; typed API contracts; largest hiring pool; SaaS reuses everything | React discipline needed to stay simple | **Recommended** |
| B. Vue 3 + TS | Gentler curve | Smaller BG pool; no decisive advantage | Rejected |
| C. Server-rendered (Jinja/HTMX) | Least JS | Kanban drag-and-drop, optimistic UI and PWA shell fight the model; SaaS UI would be rebuilt | Rejected |

PWA stance (PO directive #1): web app manifest + installable shell, **no offline data
sync**. Constraint to record: browsers grant full PWA install + service worker only
in secure contexts — `localhost` qualifies (the server PC), plain `http://LAN-IP`
does not. V1 plan: manifest for all, full install prompt on the server machine,
optional "trusted LAN HTTPS" installer step (local certificate) as an advanced
feature. This is OQ-A2.

### D5. Deployment & packaging (the make-or-break decision)

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. Native Windows installer** producing two auto-started services (ServiceFlow app+worker; bundled PostgreSQL), plus a small tray/status app (health dot, open-app button, backup-now, support package) | No prerequisites (no Docker, no runtimes to install); survives reboots; antivirus-friendly signed binaries; matches "one PC at the counter" reality | We own the installer/updater engineering | **Recommended** |
| B. Docker Desktop + Compose on the shop PC | Dev/prod parity | Docker Desktop on random shop Windows machines (WSL2, licensing, updates, virtualization BIOS flags) is support hell for non-technical users | Rejected for customer machines (retained for development) |
| C. Electron desktop app embedding everything | Familiar install UX | Single-machine bias fights the multi-user LAN requirement; browser clients still needed anyway | Rejected |

Update model (PO-relevant): Owner-triggered in-app update → download signed package →
**automatic pre-update verified backup** → apply → migrate → health check → automatic
rollback on failure. No silent updates on production shop data; no manual MSI mailing.

### D6. Background work

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. In-process job runner**: persistent `jobs` table in the DB + async workers inside the app service + cron-like schedules | Zero extra infrastructure; jobs survive restarts (table, not memory); single artifact to operate | Jobs share process resources — fine at our volumes | **Recommended** |
| B. Separate worker service (Celery/Redis-class) | Isolation, scale | A broker + second service on a shop PC for ~20 jobs/day is indefensible | Rejected (reopen at SaaS scale) |
| C. No background processing | Simplest | Verified backups, license refresh, HEIC conversion, "ready N days" reminders and update checks are inherently background | Rejected — the PO made several of these MVP features |

V1 job inventory: nightly backup + restore-verification, license refresh, update
check, HEIC→JPEG + thumbnails, ready-too-long reminder tasks, support-package
assembly, retention/GDPR sweeps.

### D7. File storage (photos, documents, generated PDFs)

| Option | Verdict & reasoning |
|---|---|
| **A. Local filesystem behind a storage port** (interface), structured content-addressed paths, included in backup artifact | **Recommended.** Trivial ops, fast LAN serving, and the port swaps to S3-compatible storage in SaaS without touching the domain. |
| B. Blobs in PostgreSQL | Single backup artifact is tempting, but DB bloat, memory pressure and slow dumps at 50–100 GB of photos kill it. |
| C. Local MinIO (S3 API now) | API parity with SaaS, but a third service on the shop PC for zero V1 benefit — the port gives parity at the interface level instead. |

### D8. Authentication & sessions (LAN)

| Option | Verdict & reasoning |
|---|---|
| **A. Server-side sessions, HttpOnly cookies, CSRF protection + per-user PIN fast-switch on shared terminals** | **Recommended.** Simple, revocable, browser-native; PIN switch keeps the timeline's "who" truthful at the counter (full password login per device per day; PIN re-identifies the user per action window). |
| B. JWT bearer tokens | Solves distribution problems this LAN app doesn't have; localStorage XSS surface; revocation complexity. Rejected. |
| C. Windows-integrated auth | Assumes domain-joined machines small shops don't have. Rejected. |

### D9. Licensing & subscription validation (Q1 decision made concrete)

| Option | Verdict & reasoning |
|---|---|
| **A. Signed offline-verifiable license tokens + periodic online refresh + grace period** | **Recommended.** App holds a vendor-signed token (company, plan, expiry); refreshes silently when internet exists; full function through a **30-day offline grace** (OQ-A1); expiry/lapse degrades to **read-only + export always available** — customer data is never hostage. Owner sees license state in settings; platform admin (vendor) can extend/override server-side. |
| B. Always-online checks | Violates "no internet required for daily work". Rejected. |
| C. Manual keys / honor system | No subscription enforcement, no telemetry for support. Rejected. |

### D10. Search

| Option | Verdict & reasoning |
|---|---|
| **A. PostgreSQL: normalized shadow columns (digits-only phones/IMEI/VIN, Cyrillic/Latin transliteration) + pg_trgm indexes** | **Recommended.** Sub-100 ms at our volumes; zero infrastructure; the normalization rules are domain logic reusable in SaaS. |
| B. External engine (Elastic/Meili) | Third service, sync pipeline — for 15 k orders/year. Rejected (SaaS-scale reopen trigger). |
| C. Plain `LIKE` | Fails Cyrillic/Latin and formatting tolerance requirements. Rejected. |

## 3. Cross-cutting evaluations (Part 6 checklist)

- **Async/event-driven?** In-process domain events (synchronous dispatch, same
  transaction) feed timeline writes and future notification hooks. No broker, no
  cross-process eventing in V1.
- **Caching?** None. The database fits in RAM; premature caching is a bug farm.
- **Audit logging?** The domain Timeline covers business history (01 §BR-5); a thin
  technical audit (logins, license events, backup/restore, GDPR actions, settings
  changes) goes to structured logs + a small admin-visible table.
- **Soft delete?** Archive flags per domain (01 §BR-8); hard delete only via GDPR
  anonymization and retention sweeps.
- **Versioning?** No entity versioning (timeline suffices — 01 §Diagnosis decision).
  API surface versioned as `/api/v1` with frozen contracts at implementation start.
- **i18n?** Bulgarian-only UI at launch, every string externalized from day one
  (key-based catalog); backend emits message codes, never prose.
- **Health checks?** (PO directive #5) `/health` endpoint + tray indicator: DB
  reachable, disk space, last backup age + last restore-verification result, license
  state, pending jobs. Red states produce plain-Bulgarian guidance.

## 4. The minimal vendor cloud (surfaced explicitly)

Subscription licensing (Q1) means V1 is not 100 % vendor-infrastructure-free. The
vendor side is deliberately tiny — one small service + static hosting:

1. **License API** — activation, refresh, plan state; admin console for the vendor
   (extend, suspend, override) — this is the PO's "control over all subscriptions"
   from the earlier concept, surviving here in its correct V1 form.
2. **Update feed** — signed release packages + release notes (static hosting + CDN).
3. **Support package inbox** — optional upload target (packages can also be exported
   to file and sent manually).

No customer business data ever flows to the vendor cloud — only license telemetry,
version info, and Owner-initiated support packages (anonymized metadata by design).

## 5. Recommended Architecture — one picture

```
SHOP LAN                                          VENDOR CLOUD (minimal)
┌─────────────────────────────────────────┐       ┌──────────────────────┐
│ Windows "server" PC (always on)         │       │ License API + admin  │
│ ┌─────────────────────────────────────┐ │  TLS  │ Update feed (signed) │
│ │ ServiceFlow service (one process)   │◄├──────►│ Support pkg inbox    │
│ │  API (FastAPI) · domain modules     │ │(only: └──────────────────────┘
│ │  in-proc jobs · PDF gen · search    │ │ license, updates,
│ │  serves SPA/PWA shell               │ │ support pkgs)
│ └──────────┬────────────────┬─────────┘ │
│ ┌──────────┴───────┐ ┌──────┴─────────┐ │      Browsers on LAN clients
│ │ PostgreSQL (svc, │ │ File storage   │ │◄───  (counter PC, tablets,
│ │ bundled, private)│ │ (local, ported)│ │      phones) — Bulgarian UI
│ └──────────────────┘ └────────────────┘ │
│  Tray app: health · backup now · support│
│  Backup artifact: DB dump + files + cfg │──► USB / network / cloud folder
└─────────────────────────────────────────┘      (restore-verified nightly)
```

### Module boundaries (enforced by import rules)

```
shared_kernel   ids, money/currency abstraction (Q3), domain events, clock
identity        Company, User, roles/permissions, sessions, PIN switch
customers       Customer (+ GDPR anonymization)
assets          AssetType (seeded field definitions), Asset, identifiers
service_orders  ServiceOrder aggregate: statuses, diagnosis, tasks, parts,
                labor, accessories · transition matrix enforcement
commercial      Commercial Documents & Invoicing: Invoice, Payment,
                DocumentSequence (PO naming directive)
timeline        append-only events, subscribed to domain events
attachments     storage port, HEIC/thumbnails, stage tags
search          normalization + query across modules (read-only access)
contacts        ContactRecords
platform        license client, backup/restore + verification, health,
                updater client, support package, jobs runner, settings
```

Dependency direction: everything may depend on `shared_kernel`; `timeline` and
`search` observe others; `platform` knows infrastructure, never domain internals;
domain modules never import `platform`. **Deployment location is invisible to domain
modules** — that is the entire SaaS migration bet.

## 6. SaaS Migration Strategy (design now, build in V2)

1. `company_id` exists on every domain record from the first migration — exactly one
   value locally; multi-tenant SaaS is a cardinality change + enforcement layer, not
   a schema rewrite.
2. The **versioned export/import format** (full company data + files manifest) is
   simultaneously: the backup artifact, the GDPR company export, and the
   local→SaaS onboarding path. One format, three obligations, tested nightly by the
   restore-verifier.
3. Ports isolate everything that changes in the cloud: storage (fs→S3), auth
   (sessions stay, IdP optional), licensing (local token→subscription service),
   jobs (in-proc→queue if scale demands).
4. Same PostgreSQL engine, same migrations, same domain code.

## 7. Major Risks

| Risk | Mitigation |
|---|---|
| Bundled PostgreSQL ops on shop PCs (highest) | Installer owns everything (silent install, private instance, auto-restart, upgrade automation); Stage-0 spike **must** prove this before schema work; SQLite exit ramp documented in ADR-002 with a deadline |
| Installer/updater engineering underestimated | Treated as a product module with acceptance criteria (backup-before-update, rollback), not a release afterthought |
| PWA secure-context on LAN | Manifest-only fallback everywhere; full install on server PC; optional HTTPS provisioning step (OQ-A2) |
| Vendor cloud availability vs. license checks | 30-day offline grace; read-only (never lockout) degradation; data export always works |
| Invoice legal correctness | Isolated in `commercial` module; accountant review is a release gate (03_MVP scope) |
| Shop PC hygiene (sleep, antivirus, full disk) | Health checks with plain-Bulgarian remediation; disk-space warnings; documented AV exclusions applied by installer |

## 8. ADR Candidates (to be written at architecture freeze)

ADR-001 Modular monolith (D1) · ADR-002 Bundled PostgreSQL + SQLite exit ramp (D2) ·
ADR-003 Python/FastAPI backend (D3) · ADR-004 React/TS frontend + PWA stance (D4) ·
ADR-005 Native installer, two services + tray (D5) · ADR-006 DB-backed in-process
jobs (D6) · ADR-007 Storage port over local filesystem (D7) · ADR-008 Session auth +
PIN switching (D8) · ADR-009 Signed license tokens + 30-day grace + read-only
degradation (D9) · ADR-010 PostgreSQL search w/ normalization (D10) · ADR-011
In-process domain events → timeline (§3) · ADR-012 Export/import format = backup =
GDPR export = SaaS path (§6) · ADR-013 company_id from day one (§6) · ADR-014
Owner-triggered updates with auto-backup/rollback (D5) · ADR-015 i18n
externalization, Bulgarian-only launch (§3).

## 9. Open Questions (architecture-level, for PO)

- **OQ-A1** License offline grace: 30 days proposed — confirm? (Longer is friendlier,
  weaker enforcement.)
- **OQ-A2** LAN HTTPS provisioning as an optional installer step (enables full PWA on
  client devices) — include in V1 or defer to V1.5? (Proposal: defer; manifest-only
  is enough at launch.)
- **OQ-A3** Anonymous error telemetry to the vendor (opt-in checkbox at setup,
  crash reports only, no business data) — include in V1? (Proposal: yes, opt-in;
  transforms support economics.)
- **OQ-A4** Vendor license admin console: minimal web UI in V1 (list installs, plan
  state, extend/suspend) — confirm scope? (Proposal: yes, minimal.)
- **OQ-A5** Server discovery on LAN: fixed `http://serviceflow.local` via mDNS +
  printed fallback IP — acceptable? (Proposal: yes, with tray "open app" button.)

**Stop.** Awaiting review. After approval: architecture freeze (write the 15 ADRs),
then the blueprint documentation package, then implementation planning — in that
order, per the framework.
