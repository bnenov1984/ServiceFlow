# 01 — Business Domain Model

Status: **Approved by Product Owner 10.07.2026 — all open questions (OQ-1…OQ-5) accepted with proposed defaults** · Date: 10.07.2026
Input: Blueprint Part 3 + Discovery Report decisions (00)
This is a business domain document. It contains no database schema, no API design,
no technology choices.

---

## 1. Domain Map

The domain answers one question: **"What is currently happening with every
customer's asset?"**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SERVICE OPERATIONS (core)                    │
│                                                                     │
│   ServiceOrder ──┬── Diagnosis (0..1)                               │
│    (center of    ├── PartLine (0..*) ─┐                             │
│                  ├── LaborLine (0..*) ┤→ CatalogItem (0..1, snapshot)│
│                  ├── AccessoryItem (0..*)                           │
│                  ├── OrderAdjustment (0..*)                         │
│                  ├── Attachment (0..*)                              │
│                  ├── ContactRecord (0..*)                           │
│                  └── TimelineEvent (append-only, 1..*)              │
└────────┬──────────────────────────────────────┬─────────────────────┘
         │                                      │
┌────────┴────────────┐              ┌──────────┴──────────────────────┐
│ CUSTOMERS & ASSETS  │              │ COMMERCIAL DOCUMENTS & INVOICING│
│  Customer ── Asset  │              │  Invoice ── InvoiceLine         │
│      │        │     │              │  Payment                        │
│      └── AssetType  │              │  DocumentSequence               │
│  CatalogItem (WP-I) │              │                                 │
└─────────────────────┘              └─────────────────────────────────┘
┌─────────────────────┐              ┌─────────────────────────────────┐
│ IDENTITY & ACCESS   │              │ PLATFORM SERVICES (product,     │
│  Company · User ·   │              │  not domain): License, Backup/  │
│  Role/Permissions   │              │  Restore, Health, SupportPackage│
└─────────────────────┘              └─────────────────────────────────┘
```

Four business areas + one platform area. Nothing bypasses the Service Order: parts,
labor, photos, communication and invoices all attach to it.

## 2. Entity Definitions

Format per entity: purpose · key attributes · lifecycle · ownership · invariants.
Attributes are business attributes, not columns.

### Company
- **Purpose:** the repair business itself; owner of all data. Exactly one per V1
  installation, modeled explicitly so SaaS multi-tenancy is a cardinality change,
  not a redesign.
- **Attributes:** name, requisites for documents (ЕИК, ДДС № if VAT-registered, МОЛ,
  address, IBAN, logo), VAT-registered flag, default settings (language, protocol
  terms text, warranty default days), operating currency (EUR in V1; abstraction per
  Q3).
- **Lifecycle:** created at installation setup; never deleted.
- **Invariants:** invoices cannot be issued until legal requisites are complete.

### User
- **Purpose:** a person who performs work; every action is attributable.
- **Attributes:** name, login, password, per-user PIN (fast counter switching), roles
  (Owner and/or Worker), active flag.
- **Lifecycle:** created by Owner → active → deactivated (never deleted; history
  keeps referring to them).
- **Invariants:** at least one active Owner must always exist. A User always belongs
  to the Company. Deactivated users cannot authenticate but remain visible in history.

### Customer
- **Purpose:** the owner of assets; the person/company we answer to.
- **Attributes:** name (required), primary phone (required, normalized), secondary
  phone, email, own main address (individuals only — free text, multi-line; a
  company's main address lives in its invoice requisites instead), is-company flag +
  invoice requisites when B2B (name, ЕИК, ДДС №, МОЛ, address), notes, created date,
  archived flag.
- **Lifecycle:** created → active → archived. An **individual** cannot be created (or
  have its phone changed) to a normalized phone that another non-anonymized
  individual already has; the user is offered the existing customer instead. A
  **company** cannot be created (or have its ЕИК changed) to an ЕИК another company
  already has. Phones shared between an individual and a company are allowed.
  *(Amended 03.11.2026 — order-workflow-revamp WP-B, Q7/Q8: supersedes the prior
  "duplicate-phone warning, never blocked" rule.)* GDPR anonymization replaces
  personal data, preserving order history integrity.
- **Invariants:** contains no repair logic; never owns attachments directly.

### AssetType
- **Purpose:** category of repaired objects; carries the type-specific field
  definitions. Seed-defined (Phone, Vehicle, Laptop, Other at launch) — new types are
  configuration releases, not code redesign. No user-facing form builder.
- **Attributes:** name, icon, ordered list of typed field definitions (text / number /
  date / choice), which fields are identifiers (searchable: IMEI, VIN, serial №, рег.
  №), which are sensitive (e.g. device passcode — masked, access logged).
- **Lifecycle:** seeded; extendable; never deleted while assets reference it.

### Asset
- **Purpose:** the central business object — everything that is repaired.
- **Attributes:** asset type, owner (Customer), label (brand + model), type-specific
  field values, identifier values (indexed for search), created date, archived flag.
- **Lifecycle:** registered at first intake → repaired many times → archived.
- **Invariants:** belongs to exactly one Customer (ownership transfer is an edit with
  timeline note — rare, supported, logged). Its history is the set of its orders.
  *(Added 04.11.2026 — order-workflow-revamp WP-C/D, Q9/Q10/Q11):* VIN and
  registration № are each unique per company when present (normalized:
  uppercase alphanumerics, Cyrillic/Latin look-alike letters folded).
  Mileage on an order is optional; when entered it must be ≥ the highest
  mileage recorded for the asset, unless the Owner confirms a lower
  reading — then the reading is stored as read, flagged „по-малък от
  предишния — потвърдено", with a mandatory timeline comment. Mileage is
  never overwritten with a different value than the one read.

### ServiceOrder — the aggregate at the center
- **Purpose:** one repair engagement; everything about a repair belongs here.
- **Attributes:** human number (`2026-00042`), customer, asset (exactly one),
  customer complaint (required), status (see 02_BUSINESS_WORKFLOW), assigned
  technician (0..1), priority (normal/high), promised date, warranty days granted on
  delivery, intake accessories checklist, estimate summary (from diagnosis), money
  totals (derived: parts + labor + adjustments), paid state (derived from payments),
  created/updated/delivered dates, archived flag, link to originating order (warranty
  returns).
- **Lifecycle:** created at intake → moves through working statuses → exactly one
  terminal outcome (Предадена / Отказана / Неремонтируема / Анулирана) → archived
  (flag). No reopening: warranty return = new order linked to the original.
  Sole exception: Owner unlock of a mistaken closure within 24 h (BR-2 amendment).
- **Invariants:**
  - Always has customer + asset + complaint from birth.
  - Status transitions only per the transition matrix (02).
  - Terminal orders accept no operational changes (except payments settling an
    outstanding balance, and archiving).
  - Every meaningful change produces a TimelineEvent in the same business
    transaction.

### Diagnosis
- **Purpose:** the professional evaluation — separate from the customer complaint
  (what the customer says) and from execution (what we did).
- **Attributes:** observed issue, cause, recommended repair, estimated cost, estimated
  duration, repairable verdict, approval requirement flag, approval record (who
  approved, when, via which channel: phone / in person / message — manual entry per
  discovery S3).
- **Lifecycle:** 0..1 per order; created during Диагностика; **edited in place, every
  edit recorded in the timeline** (no versioning — PO-approved simplification).
- **Invariants:** approval events are recorded, never implied. An order cannot leave
  Чака клиент without a recorded approval or rejection.

### Task — retired
*(Retired 04.11.2026 — order-workflow-revamp WP-H, Q17/Q17b.)* Previously:
work to be done, order-bound or company-level, with a call flag feeding a
now-also-retired dashboard widget (docs/02 §15). Removed entirely from the
product — the `Готова`-aging dashboard warning already covers the one
reminder case tasks existed for ("customer never came back for it"). The
underlying table is kept (not dropped) for a later, separate migration;
historical task-created/task-completed timeline entries are left as-is.

### PartLine
- **Purpose:** a physical component used in this repair. Lightweight by design — no
  inventory, no reservations in V1 (discovery S5) — "issued" below is a line state
  only, never a stock movement.
- **Attributes:** catalog item reference (0..1 — NULL on every line added before
  WP-I below, which stays that way forever), **snapshot** of name/code/unit cost/
  unit price taken from the catalog at add-time, quantity, state: **издадена
  (issued) · поръчана (ordered) · монтирана (installed)** *(amended 05.11.2026 —
  order-workflow-revamp WP-J, Q15/Q15b: a third state split out of the prior
  2-state "ordered"/"installed" model — Wave 2 Issue 33/migration 0022 — adding a
  line offers only "issued" or "ordered" as the starting state, "installed" is
  reached only via a later transition)*, warranty flag — on/off, defaults on,
  never affects price; the actual term is the company-wide text already printed
  on the delivery protocol, not a per-line value *(amended 05.11.2026 — WP-J,
  Q14/Q14b/Q14c, replaces the prior months-at-the-API-boundary field — migration
  0025 — entirely; a protocol frozen before this change keeps printing its stored
  months forever, never retroactively reconstructed)*.
- **Lifecycle:** added only while the order is in Диагностика, Чака клиент, Чака
  части or Ремонт — never at intake, never once Готова *(amended 05.11.2026 —
  order-workflow-revamp WP-I, Q13d, reverses Wave 2 Issue 29's "addable at
  intake")*. Marking a line поръчана from a working status offers a one-click
  suggestion to move the order to Чака части; marking the last remaining
  поръчана line издадена offers a one-click suggestion back to Ремонт — both are
  nudges only, never an automatic transition (WP-J, Q5/Q5c).
- **Invariants:** belongs to exactly one order. **Created only from a catalog
  item — no free-typed name or price, for any role** *(amended 05.11.2026 —
  WP-I, Q12a, ADR-BOS-013)*; a later catalog price change never alters an
  already-added line (BR-3). Money totals feed the order and the invoice draft.

### LaborLine
- **Purpose:** work performed, priced **from the catalog** — per operation (unit
  бр.) or per hour (unit час) *(amended 05.11.2026 — WP-I, Q12d, supersedes the
  25.09.2026 fixed-price-only framing)*.
- **Attributes:** catalog item reference (0..1), snapshot of description/code/
  unit/unit price/unit cost taken from the catalog at add-time, quantity
  (decimal — fractional for an hourly item, e.g. 1.5 ч.), optional duration info
  (unchanged — never a catalog field), performed by (0..1).
- **Lifecycle:** same allowed statuses and intake exclusion as PartLine above
  (Q13d).
- **Invariants:** belongs to exactly one order; created only from a catalog item,
  same discipline as PartLine (Q12a); feeds order totals and invoice draft; a
  later catalog price change never alters an already-added line (BR-3).

### CatalogItem *(new — order-workflow-revamp WP-I, Q12, ADR-BOS-013)*
- **Purpose:** one entry of the shop's own price list — what PartLine/LaborLine
  are created from. Flat, no categories/variants.
- **Attributes:** kind (част/труд), name, code (optional, unique per company when
  set), unit (бр./час), sale price (net), unit cost (optional, Owner-only
  visibility), archived flag.
- **Lifecycle:** Owner creates/edits/imports (CSV/Excel, dry-run preview)/
  archives; **never deleted** — existing lines keep a reference to it.
- **Owner module:** `serviceflow.catalog` (not part of the ServiceOrder
  aggregate — referenced and snapshotted, never contained).

### OrderAdjustment *(new — order-workflow-revamp WP-I, Q13, resolves OQ-5 below)*
- **Purpose:** the only way to correct an order's price (e.g. "направи го 50 €").
- **Attributes:** signed amount, mandatory reason, created by (Owner).
- **Lifecycle:** append-only — a wrong adjustment is corrected by adding an
  offsetting one, never edited or deleted.
- **Invariants:** Owner-only; feeds derived totals (BR-3); becomes a
  `source="adjustment"` line on an invoice draft created from this order;
  timeline-logged.

### AccessoryItem
- **Purpose:** what arrived with the asset at intake (charger, SIM, case, keys…) —
  belongs to the **ServiceOrder** (they accompany an intake event, not the asset
  permanently — discovery recommendation, PO-accepted).
- **Attributes:** name, quantity, returned flag (checked at delivery).
- **Invariants:** appears on the intake protocol; delivery protocol section confirms
  return.
- **Amended 04.11.2026** (order-workflow-revamp WP-H, Q16/Q16b): offered only
  for an asset type whose `accessories` flag is true (every profile except
  automotive — ADR-BOS-011 §Decision 5/8). Nothing here is profile-
  conditional on the AccessoryItem side itself: an automotive order that
  already has accessory items from before this flag existed keeps them,
  keeps them on its protocols/completion snapshot, and keeps the
  returned-flag workflow for them — only adding a *new* one is blocked for
  that asset type.

### Attachment
- **Purpose:** photos and documents evidencing the repair.
- **Attributes:** file reference, kind (photo/document), stage tag (reception /
  progress / completed / other), caption, uploaded by/at.
- **Lifecycle:** added anytime pre-terminal; soft-deleted with timeline trace.
- **Invariants:** belongs to a ServiceOrder, never directly to a Customer (blueprint
  rule, confirmed).

### ContactRecord
- **Purpose:** communication history — calls, messages, visits; manual entry in V1.
- **Attributes:** type (обаждане / имейл / съобщение / на място), timestamp, user,
  summary, direction (in/out), order reference (0..1), customer reference.
- **Invariants:** editable only by author until end of day, then frozen (keeps history
  honest while allowing typo fixes — PO may veto); always appears in timeline.

### TimelineEvent
- **Purpose:** trustworthy append-only history; the answer to the core business
  question over time.
- **Attributes:** order reference, event type (see §5), actor (user or system),
  timestamp, human-readable summary data.
- **Invariants:** never edited, never deleted by users; written in the same business
  transaction as the change it records; retention follows the order.

### Invoice (+ InvoiceLine)
- **Purpose:** the commercial document for completed work. Part of **Commercial
  Documents & Invoicing** (naming per PO directive — never "Accounting").
- **Attributes:** invoice number (strictly sequential at issue time, per ЗДДС), issue
  date, tax-event date (the date the taxable event/advance payment occurred — legally
  distinct from issue date, ЗДДС чл. 114, ал. 1; schema field landed as its own
  prerequisite slice, docs/ACCOUNTANT_REVIEW.md §2 — supplied explicitly on the Issue
  request, never backend-derived, D1), seller requisites (snapshot of Company), buyer
  requisites (snapshot of Customer), lines (imported from labor lines, part lines,
  plus manual lines and adjustments), VAT treatment per company registration mode,
  totals, currency (EUR; currency-abstracted), state, reference to annulled
  predecessor (corrections), order reference.
- **Lifecycle:** **Draft → Issued → (Annulled)**. Drafts are editable and unnumbered.
  Issue assigns the next number and freezes the document. Corrections = annul +
  reissue; issued invoices are never edited (legal requirement). **Phase A Issue
  implemented, buyer support extended to domestic companies, seller support
  extended to VAT-registered companies** (docs/ACCOUNTANT_REVIEW.md 'RepairFlow
  Invoice V1 Freeze' §5 / §4 B1 / §6): the seller may be non-VAT-registered, or
  VAT-registered at the single standard 20% rate (`net = Σ(qty×unit_price)`,
  `vat = round(net×0.20, 2)` — one calculation on the invoice total, `ROUND_HALF_UP`
  — the frozen V1 rounding rule, implemented pending professional confirmation).
  The buyer may be an individual, or a domestic company (VAT-registered or not,
  given a known `vat_registered` status and, when VAT-registered, a valid VAT
  number); a company buyer whose VAT-registration status is not yet established is
  explicitly rejected. The buyer's VAT status never changes the seller's VAT
  calculation, in either direction. Mixed VAT rates, reverse charge, 0%-rated
  supplies, credit/debit notes, and annul/reissue remain future slices.
  **Phase A PDF implemented** (`GET /invoices/{id}/invoice.pdf`,
  docs/ACCOUNTANT_REVIEW.md §11): every issued Phase-A invoice has a printable/
  downloadable PDF representation, generated on demand from the frozen
  Invoice/InvoiceLine snapshot — later edits to Company/Customer master data
  never alter a previously issued invoice's PDF. Drafts have no PDF.
  **Central invoice workspace implemented** (`/invoices`, RepairFlow nav item
  "Фактури" — a history/list view, not a new creation entry point; invoices
  are still created only from a Service Order's own Invoice section): GET
  /invoices' list response batch-enriches each row with order_number/
  customer_name/total. customer_name is dual-sourced by design — an issued
  row's buyer identity is the invoice's own frozen `buyer` snapshot (never
  live Customer data, even for a malformed/legacy snapshot); a draft row has
  no snapshot yet, so it falls back to the live Customer name. `total` is
  the frozen `gross` once an invoice carries one, otherwise the live sum of
  the draft's current lines — one field, two semantics, documented rather
  than hidden behind a single ambiguous name.
  **Standalone Invoice Detail implemented** (`/invoices/{id}`,
  invoices/InvoiceDetailPage.tsx): the central list's "Отвори" opens the
  Invoice itself here, not the originating order — the Order number is its
  own separate link to `/orders/{order_id}`, kept deliberately distinct so
  "open the invoice" and "open the order" are never the same click. Draft
  editing/Issue and the issued read-only view are the exact same
  `InvoiceDraftEditor`/`IssuedInvoiceView` components `order/InvoiceCard.tsx`
  already renders inside a Service Order — extracted, not duplicated, so
  there is one Invoice presentation reused from two navigation contexts.
  Both read/write through the same `queryKeys.invoice(id)` cache, so an
  Issue performed from either context is immediately visible from the
  other.
- **Invariants:** numbering has no gaps and no reuse; requisite snapshots make the
  document self-contained even if company/customer data later changes; invoices are
  **optional per order** (B2C walk-ins often need none) and possible on Отказана
  orders (diagnostic fee).
- **Open legal items** for the accountant review are listed in §7.

### Payment
- **Purpose:** money received (or returned) — one unified mechanism (discovery §3.6,
  PO-approved).
- **Attributes:** amount, method (в брой / карта / банков превод), date, note, refund
  flag, received by, order reference, optional invoice reference.
- **Lifecycle:** recorded; corrections by an offsetting record, not deletion.
- **Invariants:** deposit = payment before completion; partial = sum < total; order
  "paid" state is always derived, never stored as an independent editable flag.
  Fiscal (cash register) receipts are outside the product — the shop's fiscal device
  handles them.

### DocumentSequence
- **Purpose:** owns strictly-sequential numbering for invoices (and order numbers).
- **Invariants:** gapless for invoices; concurrent issue requests serialize.

### Future entities (declared, not designed)
Notification, InventoryItem, Supplier — extension points only; no V1 behavior.

## 3. Relationships

```
Company 1──* User
Company 1──* Customer 1──* Asset *──1 AssetType
Company 1──* CatalogItem                        (order-workflow-revamp WP-I)
Customer 1──* ServiceOrder *──1 Asset          (order's asset belongs to its customer)
ServiceOrder 1──0..1 Diagnosis
ServiceOrder 1──* PartLine | LaborLine | AccessoryItem | Attachment | OrderAdjustment
PartLine | LaborLine *──0..1 CatalogItem        (snapshotted at add-time, BR-3)
ServiceOrder 1──* TimelineEvent | ContactRecord(optional link)
ServiceOrder 1──* Payment *──0..1 Invoice
ServiceOrder 1──* Invoice (typically 0..1 active; annulled predecessors retained)
ServiceOrder 0..1──* ServiceOrder               (warranty return → original)
```

Consistency rule: an order's asset must belong to the order's customer at creation
time; later asset ownership transfer does not rewrite history.

## 4. Aggregate Proposal

Analysis basis: transaction boundaries, ownership, concurrency (per blueprint Part 3 —
aggregates are proposed, not assumed).

| Aggregate root | Contains | Why this boundary |
|---|---|---|
| **ServiceOrder** | Diagnosis, PartLines, LaborLines, AccessoryItems, OrderAdjustments, status | These change together under one business action (estimate, parts arrival, repair, price correction) and share invariants (totals, status rules). Single-user-at-a-time editing per order is realistic for 1–20 person shops; optimistic concurrency with clear conflict messages. |
| **CatalogItem** *(WP-I)* | — | Referenced, not contained — PartLine/LaborLine snapshot its fields at add-time (BR-3) rather than live-joining it; a later catalog edit must never retroactively change an existing order. |
| **Invoice** | InvoiceLines | Immutability after issue + gapless numbering demand a hard boundary; issue is its own transaction against DocumentSequence. |
| **Customer** | — (Assets referenced, not contained) | Assets have independent lifecycles and are referenced by orders; containing them would drag order history into customer edits. |
| **Asset** | field values | Simple entity-as-aggregate. |
| **Company**, **User** | — | Identity context; low write volume. |

Deliberately **outside** any aggregate (independent lifecycles, high concurrency, no
shared invariants): **Attachment**, **ContactRecord**, **Payment**,
**TimelineEvent** — each references the order; each writes its own timeline event
transactionally. This keeps two workers from conflicting when one records a contact
while another uploads a photo on the same order.

## 5. Domain Events (identified, not event-sourced)

OrderCreated · DiagnosisRecorded · DiagnosisUpdated · EstimateApprovalRequested ·
EstimateApproved · EstimateRejected · StatusChanged · TechnicianAssigned ·
PartAdded / PartOrdered / PartIssued *(renamed/extended 05.11.2026 — WP-J, Q15:
PartReceived is a pre-Issue-33 legacy type, no longer emitted, historical
entries only)* · LaborAdded ·
OrderAdjustmentAdded *(new 05.11.2026 — WP-I, Q13)* ·
TaskCreated / TaskCompleted / TaskReopened (retired WP-H 04.11.2026 — no longer
emitted, historical timeline entries only) ·
NoteOrContactRecorded · AttachmentAdded · OrderReady · OrderDelivered ·
OrderCancelled / OrderNotRepairable · **OrderUnlocked** (BR-2 admin exception:
Owner, ≤24 h, reason) · InvoiceIssued · InvoiceAnnulled ·
PaymentRecorded / PaymentRefunded · WarrantyReturnOpened · CustomerAnonymized

Every event above generates a TimelineEvent. The list also defines the future
notification surface (V1.5+) without implementing it.

## 6. Business Rules (domain-level)

- BR-1 Nothing bypasses the Service Order: parts, labor, photos, communication and
  invoices exist only in the context of an order. *(Amended 04.11.2026 — WP-H: this
  rule's one exception, company-level tasks, is retired along with the Task entity
  itself; BR-1 is now exceptionless.)*
- BR-2 Exactly one terminal outcome per order; terminal orders are not reopened;
  follow-up work = new linked order. *(Amended 11.07.2026, PO-approved via the 07
  change process:)* one strictly limited administrative exception — the **Owner may
  unlock a mistakenly closed order within 24 hours** of the terminal transition,
  with a mandatory reason; the order returns to the status it held immediately
  before closure and the unlock is timeline-recorded. Rationale: prevents junk
  follow-up orders caused by a mis-click without weakening history integrity —
  the exception is visible, attributed, bounded, and Owner-only.
- BR-3 Money totals and paid state are always derived (lines, payments) — never
  hand-edited numbers.
- BR-4 Issued commercial documents are immutable; corrections create new documents.
- BR-5 Every state-changing action is attributable to a user and timeline-recorded.
- BR-6 Identifier fields (IMEI, VIN, serial, рег. №, phone) are normalized on entry
  and searchable.
- BR-7 An order in Чака клиент requires a recorded approval/rejection to proceed.
- BR-8 Deleting is archiving; hard deletion exists only as GDPR anonymization for
  Customer personal data.
- BR-9 Accessories recorded at intake must be explicitly confirmed returned at
  delivery. *(Amended 04.11.2026 — WP-H, Q16/Q16b: offered at intake only for an
  asset type with `accessories: true` — automotive excluded; already-recorded
  items on any order, automotive included, still go through this same
  confirm-returned rule.)*
- BR-10 Sensitive asset fields (passcodes) are masked by default; every reveal is
  logged. (Final inclusion pending security review.)

## 7. Risks & Open Questions (domain)

**Risks**
- Invoice legal correctness (VAT modes, numbering, annulment mechanics) — mitigated
  by accountant review (Q2 decision) before release; the domain isolates all of it in
  Commercial Documents & Invoicing.
- Derived totals vs. shop habits ("just make it 50 €") — mitigated by manual invoice
  lines and an order-level adjustment line, keeping BR-3 intact.
- Aggregate too big: if real shops show heavy concurrent editing inside one order,
  PartLine/LaborLine may need to leave the aggregate. Optimistic concurrency + pilot
  feedback will tell; boundary change is contained.

**Open questions for PO**
- OQ-1 ContactRecord edit window ("author-only until end of day") — accept or make
  records immutable immediately?
- OQ-2 Should Отказана orders require a recorded rejection reason (one line)?
  (Recommend: yes — future analytics gold, zero UX cost.)
- OQ-3 Warranty default: per-company default days with per-order override — accept?
- OQ-4 Asset ownership transfer (customer sold the phone): keep as simple owner edit
  with timeline note — accept?
- OQ-5 Order-level discount/adjustment line: single signed amount with reason —
  accept? (Keeps BR-3 while matching counter reality.) **Implemented
  05.11.2026** (order-workflow-revamp WP-I, Q13) as `OrderAdjustment` — see
  its own entity section above.

**Stop.** Awaiting review together with 02_BUSINESS_WORKFLOW.md before Architecture
Discovery (Part 6).
