# ServiceFlow — Product Discovery Report

Status: **PASS — reviewed and approved by Product Owner on 10.07.2026** (see Resolved Decisions below)
Date: 10.07.2026
Input: Master Product Blueprint Prompt v1.0, Parts 1–6
Scope of this document: Product Discovery only (Part 5 output format). No architecture,
no database design, no blueprint documents.

---

## Resolved Decisions (Product Owner review, 10.07.2026)

| # | Question | Decision |
|---|----------|----------|
| Q1 | Commercial model | **Subscription, even for local deployment** (indicative 39–49 €/month). App runs locally; license validated periodically (grace behavior to be defined in architecture). No perpetual licenses. Funds updates and support. |
| Q2 | Invoicing depth | **Real ЗДДС-compliant invoices in V1**, mandatory review by a Bulgarian accountant before release. |
| Q3 | Currency | **EUR in the frontend; currency abstraction in the backend** (multi-currency-capable domain, single currency exposed in V1). |
| Q4 | Hardware baseline | **Confirmed**: one Windows PC + A4 printer minimum. Label printer → V1.5. |
| Q5 | Notifications | **SMS/Viber out of V1**, targeted V1.5. |

Additional PO directives:

1. **Keep PWA** (installable app shell) but do **not** design offline data sync.
2. The invoicing area is named **"Commercial Documents & Invoicing"** — never "Accounting".
3. Adopt the **simplified status model** (§3.3).
4. Adopt the **unified Payment model** (§3.6).
5. **Backup + Restore + Health Check + Diagnostics are MVP features.** Every backup
   must be provably restorable — automated restore verification, not just backup.
6. **Remote Support is V1 scope**: Owner can generate a **Support Package** (logs,
   config, diagnostics, app version, environment info, anonymized database metadata —
   never customer business data) for remote troubleshooting.

Next stage approved: proceed toward Architecture Discovery via Part 3 (Domain Model)
and Part 4 (Business Workflow), which architecture must be derived from.

---

## 1. Executive Summary

ServiceFlow is a browser-based Service Management Platform for Bulgarian repair
businesses (1–20 employees), covering the full lifecycle: Customer → Asset → Service
Order → Diagnosis → Tasks → Parts → Labor → Timeline → Invoice → Payment → Delivery →
History. Version 1 is a **locally deployed, single-company** installation (Windows,
LAN, multi-user, no internet dependency for daily work); Version 2+ evolves into a
cloud SaaS sharing the same domain core. It is explicitly not an ERP, not accounting
software, not a CRM, not inventory software.

The concept is commercially sound and the pain is real — fragmentation across
notebooks, Excel, Viber and memory is the accurately diagnosed problem, and "the
easiest way to organize repair work" is the right positioning.

Discovery found **three dominant risk areas** that will decide success or failure,
none of them in the domain model:

1. **Local deployment operations** — installing, updating, backing up and supporting
   a PostgreSQL-backed web application on shop-owned Windows machines, for
   non-technical customers, at scale. This is where products of this type die. The
   brief specifies the deployment model but not the commercial model around it
   (licensing, installation, support, updates) — these are blocking questions.
2. **Bulgarian invoicing legality** — invoices in Bulgaria carry legal requirements
   (mandatory requisites, sequential numbering under ЗДДС, VAT treatment, fiscal
   receipt rules for cash under Наредба Н-18, and euro denomination since
   01.01.2026). "Repair-related invoicing, not accounting" is the right instinct,
   but the boundary must be drawn precisely and reviewed by an accountant/lawyer.
3. **Scope pressure vs. the simplicity promise** — the proposed 12-status workflow,
   versioned diagnosis, and full payment taxonomy (partial/advance/deposit/refund)
   all pull against "understandable in minutes." Discovery recommends concrete cuts
   (§6) that preserve every real business capability.

One assumption in the brief is internally contradictory (PWA/offline vs. shared local
database — §3) and one is missing entirely (currency: Bulgaria has used the euro since
01.01.2026). Five blocking questions (§7) must be answered before Part 3 (Domain
Model) begins.

## 2. Strengths

- **Generic Asset core.** Modeling every repaired object as an Asset with an Asset
  Type is the single most important architectural instinct in the brief. It is what
  lets one product serve phone, auto, drone and coffee-machine shops.
- **The lifecycle matches reality — including failure paths.** Explicitly modeling
  Customer Rejects Estimate, Not Repairable, Customer Never Returns, Wrong Diagnosis,
  Additional Damage Found and Warranty Return distinguishes this from naive happy-path
  designs. Most competitor products handle these badly.
- **Trustworthy timeline.** Append-only, never user-edited history answers the core
  business question ("what is happening with every asset?") and creates accountability
  small shops currently lack entirely.
- **Explicit non-goals.** ERP/accounting/CRM/inventory exclusions, "feature count is
  not success," and the priority ladder (business value → UX → simplicity …) are
  strong guardrails against the most likely failure mode (bloat).
- **Local-first fits the market's psychology.** Data ownership, one-time-cost
  preference, and distrust of subscriptions are genuine traits of Bulgarian
  micro-businesses. Local V1 also removes hosting cost and GDPR-processor burden from
  the vendor at the start.
- **Minimal roles.** Owner + Worker with permission-based internals is exactly right
  for 1–20 employee shops.
- **One product, two deployment models** is the correct framing for the SaaS future —
  it forces deployment concerns out of the domain from day one.

## 3. Weaknesses, Contradictions, Assumptions Challenged

### 3.1 "Progressive Web App" contradicts the deployment model (contradiction)
A PWA implies service workers, HTTPS, and an offline/caching story. But: (a) the app's
data lives in a shared LAN database — if the local server is up, "offline" is
meaningless; if it's down, cached UI without data writes is useless and multi-user
offline sync is a notoriously hard problem the brief rightly never asked for;
(b) HTTPS on a LAN requires self-signed certificate gymnastics on every client.
**Recommendation:** a responsive browser app served by the local server. "Installable
shortcut" convenience — fine. Service-worker offline sync — cut. The offline
requirement is genuinely satisfied by the *server* being local, not by the *browser*
caching.

### 3.2 "Not accounting software" vs. invoicing + payments + corrections (tension)
Issuing invoices is a regulated activity: mandatory requisites (name, ЕИК, ДДС №,
МОЛ, addresses), strictly sequential 10-digit numbering under ЗДДС, VAT rules that
differ for VAT-registered vs. non-registered businesses (many 1–5 person shops are
**not** VAT-registered), credit/debit notes for corrections, and euro amounts since
01.01.2026. Separately, cash payments legally require a receipt from a fiscal device —
which is hardware outside our product. "Invoice correction → Invoice Updated" from
Part 4 is legally wrong once an invoice is issued: issued invoices are corrected by
credit note or annulment, not editing.
**Recommendation:** V1 issues invoices with correct requisites and numbering, supports
annulment + reissue (not in-place editing of issued invoices), stores the fiscal-
receipt question as out of scope (the shop's fiscal device handles cash receipts), and
the exact boundary is confirmed by an accountant. Also note: for B2C walk-ins, most
shops issue **no invoice at all** unless the customer requests one — the main flow in
Part 4 makes invoicing mandatory before delivery. It must be optional per order.

### 3.3 Twelve statuses is too many (challenged)
Received, Diagnosis, Waiting Customer, Waiting Parts, Repair, Testing, Ready,
Delivered, Closed, Cancelled, Not Repairable, Archived — as Kanban columns this fails
the "understand Kanban immediately" success metric.
**Recommendation:** 7 working statuses + terminal outcomes + an archive *flag*:
- Working: Приета → Диагностика → Чака клиент → Чака части → Ремонт → Тестване
  (optional, toggleable) → Готова
- Terminal: Предадена (success) · Отказана (estimate rejected) · Неремонтируема ·
  Анулирана (mistake/duplicate)
- **Closed merges into Предадена** (delivery closes the order; a separate Closed state
  adds a click with no information).
- **Archived is a flag/retention state, not a workflow status** — it applies equally
  to all terminal outcomes and never appears on the board.
"Customer Never Returns → Stored" is handled by Готова + elapsed-time warning +
reminder task, not by another status.

### 3.4 Local deployment's operational reality is unaddressed (risk)
The brief asks for "simple deployment, simple backup, simple update" but the hard
questions are commercial: Who installs it (vendor remote session? self-install
wizard?), who fixes it when Windows Update reboots the machine or antivirus
quarantines the database, how updates are distributed to N offline-ish sites, how
licenses are enforced, and what the pricing model is. A shop's "server" will be a
counter PC that gets turned off at night.
**Recommendation:** treat installer, updater, automated local backup (with "backup to
USB/cloud drive" UX) and license/activation as first-class V1 features with their own
discovery — they are product surface, not DevOps afterthoughts. Blocking question Q1.

### 3.5 Versioned Diagnosis (challenged)
Versioning adds UI and concept weight for an audit need the Timeline already covers.
**Recommendation:** one editable Diagnosis per order; every edit writes a timeline
event; "wrong diagnosis" flow = status back to Диагностика + edit + timeline trail.
No version entities.

### 3.6 Payment taxonomy (challenged)
Cash/card/bank/multiple/partial/advance/deposit/refund is eight concepts.
**Recommendation:** one mechanism — a Payment record (amount, method: в брой / карта /
банка, date, note, refund flag), many per order. Deposit = a payment before
completion. Partial = sum(payments) < total. Refund = flagged payment. Zero special
logic, full coverage.

### 3.7 Assumption: internet unreliability
Bulgarian urban internet is among Europe's fastest and most reliable; "no internet"
is rarely the true motivation. The honest drivers of local-first are data ownership,
cost, and vendor trust — which remain valid. Worth being clear-eyed: the offline
argument should not be used to reject high-value connected features (SMS/Viber "ready
for pickup" notifications are arguably the most-desired feature in this market —
recommended for V1.5, degrading gracefully when offline).

### 3.8 Missing currency definition
The brief never states a currency. Bulgaria adopted the **euro on 01.01.2026**; the
dual BGN/EUR display obligation expires in mid-2026, effectively before launch.
Recommendation: EUR everywhere, formatting configurable, no multi-currency (N-blocking
question Q3 to confirm).

## 4. Missing Requirements

Grouped; each becomes a business rule or blueprint item after PO input.

**Company & legal**
- Company requisites for documents: name, ЕИК, ДДС № (if registered), МОЛ, address,
  IBAN, logo. Required before the first invoice can exist.
- VAT-registered vs. non-registered operating modes (affects every price and invoice).
- Invoice numbering (sequential per ЗДДС), annulment and credit-note handling.
- Legal disclaimer boundary: cash receipts come from the shop's fiscal device;
  ServiceFlow records payments for operational tracking. Needs accountant review.
- GDPR: customer data export and delete/anonymize (shop is the data controller, but
  the product must make compliance possible).

**Operational domain**
- Service Order numbering scheme (human-readable, e.g. `2026-00042`) — referenced on
  labels, protocols, phone calls.
- Promised/estimated completion date and the definition of "overdue" (dashboards
  depend on it).
- Diagnosis fee practice: shops commonly charge a diagnostic fee when the customer
  declines the repair — the rejected-estimate flow must still allow an invoice/payment.
- Accessories: proposed home is the **Service Order** (they arrive with an intake
  event, not with the asset permanently) — checklist + photos at reception.
- Duplicate customer detection (normalize phone numbers; warn, don't block).
- Concurrency: two workers editing the same order / dragging the same card.
- Technician absence: bulk reassignment of orders/tasks.
- Warranty on completed repairs: warranty period per order (days), shown on delivery
  documents; warranty-return orders link to the original.
- Search normalization: Cyrillic/Latin (Иван/Ivan), digits-only matching for phones,
  IMEI, VIN.

**Product & platform**
- Authentication at the counter: shared PC, fast user switching (per-user PIN) or full
  login? Affects timeline trustworthiness (who did what).
- Printing hardware: A4 assumed; are thermal receipt printers or label printers V1?
  (Labels with order № on devices are common practice.)
- Photo/attachment limits, storage growth on a shop PC, retention policy.
- Backup: schedule, destination (external drive/cloud folder), restore UX, and who is
  responsible.
- Update channel: how a local install learns about and applies updates.
- Licensing/activation model and anti-copy stance.
- Language policy: Bulgarian-only V1 with proper i18n externalization (no hardcoded
  strings), or full bilingual? (Recommend the former.)
- Hardware baseline: minimum spec, one always-on machine as server.
- Price list / service catalog (predefined common repairs with prices) — not requested
  in the brief but a major speed and consistency win; proposed for V1.5.

## 5. Recommended Changes

1. **Replace PWA/offline with a LAN-served responsive web app** (§3.1).
2. **Make invoicing optional per order**; the mandatory printed artifact at intake is
   the **приемо-предавателен протокол** (intake/handover protocol) — it, not the
   invoice, is the document every BG shop hands over daily.
3. **Adopt the reduced status model** (§3.3) with statuses carrying fixed semantic
   kinds (working / ready / terminal-success / terminal-failure) so dashboard, Kanban
   and rules don't depend on display names.
4. **Single editable Diagnosis + timeline trail**, no versioning (§3.5).
5. **Labor as fixed-price lines** (description + price, optional quantity) — matches
   how BG shops actually price (per operation, price-list mentality). Time-based labor
   and timers: future. This answers Part 4's labor question.
6. **Parts as lightweight order lines** (name, cost, sell price, status:
   needed/ordered/received) with no stock, no warehouse, no reservations in V1.
   Inventory-lite (counts + low-stock warnings) in V1.5 only if validated.
7. **Unified Payment record** (§3.6).
8. **Issued invoices are immutable** — annul + reissue, never edit (§3.2).
9. **V1 PDF set = 2 documents**: intake/handover protocol and invoice. Diagnosis/
   estimate printout, warranty certificate, delivery protocol — V1.5 candidates. (The
   delivery signature fits on the protocol; a separate document adds paper, not value.)
10. **Add per-user PIN fast-switching** on shared counter PCs so the timeline's "who"
    stays truthful (pending Q4 hardware confirmation).
11. **Treat installer / updater / backup / licensing as V1 product features** with
    their own acceptance criteria (§3.4).
12. **Plan SMS/Viber "ready for pickup" notifications as the headline V1.5 feature** —
    highest perceived value per unit of effort in this market; requires internet,
    degrades gracefully.

## 6. Simplification Opportunities

| # | Cut / simplification | What it avoids | What still works |
|---|----------------------|----------------|------------------|
| S1 | No workflow engine; fixed status set with kind semantics; per-company rename + Testing toggle later | Config UI, transition editor, testing matrix | Full lifecycle incl. all exceptional flows |
| S2 | No dynamic form builder; Asset Types are seed-defined typed field sets (Phone, Vehicle, Laptop, Other at launch) | EAV swamp, form-designer UI | New asset types added by seed/config release, not redesign |
| S3 | No customer-approval portal; approval recorded manually (who/when/channel) as an event | Public endpoints, tokens, legal questions | The "waiting customer → approved/rejected" flow, fully traceable |
| S4 | No task dependencies/subtasks/boards; task = title, assignee, due date, done | Jira drift | Checklists per order + "call customer" reminders |
| S5 | No inventory in V1 (parts are order lines) | Warehouse module, stock accounting | Parts cost/price on orders, "waiting parts" flow |
| S6 | No reporting module in V1; filtered lists + dashboard counters | Report builder | "What needs attention today" |
| S7 | Timeline as one append-only table of typed events | Event sourcing | Trustworthy history + future activity feed |
| S8 | Two roles mapped to internal permission constants | Permission builder | Owner/Worker separation now, more roles later without rewrite |
| S9 | Archived = flag + retention rule | 12th status, board clutter | Clean history, GDPR retention hooks |
| S10 | EUR only, no multi-currency, no BGN dual display | Currency engine | Correct post-euro-adoption operation |

## 7. Open Questions

### Blocking (answers required before Part 3 — Domain Model)

- **Q1. Commercial & support model for local V1.** How is the product sold and
  operated: one-time license, annual license, or subscription-with-activation? Who
  performs installation (vendor-assisted remote install vs. self-service installer)?
  Who is the first line of support? This determines licensing, telemetry, updater and
  installer design — all V1 scope.
- **Q2. Invoicing depth.** Confirm: V1 issues real ЗДДС-compliant invoices (sequential
  numbering, requisites, VAT-registered and non-registered modes, annul+reissue), with
  fiscal receipts explicitly out of scope (shop's fiscal device). Or should V1 start
  with non-fiscal "service receipts" and add formal invoices after accountant review?
- **Q3. Currency.** Confirm EUR-only (Bulgaria in the eurozone since 01.01.2026), no
  BGN dual display at launch.
- **Q4. Hardware baseline.** Can V1 require: one always-on Windows PC (or mini-PC) as
  the server, modern browsers on clients, A4 printer? Are thermal/label printers in or
  out of V1?
- **Q5. Customer notifications.** Confirm SMS/Viber "ready for pickup" is out of V1
  and targeted for V1.5 (it conflicts with the no-internet constraint but is the
  market's most-requested capability).

### Important (before architecture freeze; proposed defaults in parentheses)

- Language policy (Bulgarian-only UI, fully externalized strings, i18n-ready).
- Counter authentication (username/password login + per-user PIN fast switch).
- Backup policy (automatic daily local backup + copy-to-folder/USB target + restore
  wizard; shop owns the responsibility, product makes it one click).
- Order numbering format (`YYYY-NNNNN` per company).
- Promised date + overdue definition (promised date passed, order not Готова/terminal).
- Diagnosis fee on declined repairs (supported: invoice possible on Отказана orders).
- Warranty period field per order + link model for warranty returns (new order
  referencing the original).
- Photo limits (10 MB/file, ~20/order, HEIC accepted and converted).
- Data retention defaults (orders kept indefinitely; GDPR delete/anonymize on demand).

### Safe to postpone

Price-list catalog details (V1.5) · inventory-lite shape (V1.5) · SaaS tenancy
specifics (V2) · reporting (V1.5+) · integrations (accounting export, VIN/IMEI lookup)
· customer self-service status page (V2).

## 8. Proposed Product Roadmap

**MVP (Version 1)** — local, single company, Bulgarian:
Customers · Assets (Phone/Vehicle/Laptop/Other, seed-typed fields, indexed
identifiers) · Service Orders (numbering, promised date, accessories checklist,
photos) · reduced status workflow + Kanban + button status change · Diagnosis (single,
timeline-tracked) · Tasks (with call reminders) · Parts as order lines · Labor as
fixed-price lines · Payments (unified record) · Optional invoices (compliant,
immutable, annul+reissue) · Intake/handover protocol PDF + Invoice PDF · Timeline ·
Dashboard (needs-attention widgets) · Global search (normalized) · Owner/Worker roles
+ PIN switch · Installer, updater, automated backup/restore, licensing · GDPR
export/delete.

**Version 1.5** — connected conveniences, same deployment:
SMS/Viber "ready" notifications · price-list/service catalog · inventory-lite (counts,
low stock) · label printing (order № stickers) · warranty certificate + estimate PDFs
· simple reports (revenue by period, orders by status/technician) · bulk reassignment.

**Version 2** — SaaS edition:
Multi-tenant cloud deployment · company self-registration + subscriptions + online
payments · central platform administration · cloud storage · data migration path from
local installs (a local V1 export must import cleanly into SaaS — this constraint is
binding on V1's data design).

**Future ideas** — customer status portal & online approvals · accounting-system
export · VIN/IMEI decoding · multi-location · public API · AI assistance (repair
summaries, suggested next actions) · marketplace of asset-type packs.

## 9. Discovery Conclusion

The product is viable and well-conceived: the domain model instinct (generic Asset,
order-centric lifecycle, trustworthy timeline) is correct, the market pain is real,
and the simplicity-first philosophy is the right differentiator. The domain itself
poses low risk.

The decisive risks are non-domain: (1) the operational and commercial model of local
Windows deployment, (2) the legal precision of Bulgarian invoicing, and (3) scope
discipline. This report proposes concrete mitigations for all three, and ten
simplifications that remove roughly a third of the implied surface area without
losing a single business capability.

**Recommended next step:** Product Owner answers Q1–Q5 and vetoes/accepts the
proposed defaults. Then proceed to Part 3 (Business Domain Model) and Part 4
(Business Workflow) — in that order, with the workflow document validating the domain
against the day-in-the-life narratives. Architecture (Part 6) follows only after both
are reviewed.

*This report intentionally contains no architecture, database, or implementation
decisions.*
