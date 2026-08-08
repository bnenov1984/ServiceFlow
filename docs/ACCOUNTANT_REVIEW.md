# Accountant Review — Invoice Issue

Status: **Law-research pass complete for the 26-item V1 checklist.** Most
items now have a law-grounded answer or a clearly bounded product decision;
a smaller set of genuinely interpretation-dependent points remain flagged
**PROFESSIONAL REVIEW REQUIRED**. · Opened: 20.07.2026 · Consolidated:
08.08.2026 · Law-research pass: 08.08.2026 · Source: docs/00 §Q2, docs/01
§7, docs/02 §11/§13, docs/08, docs/09, docs/12 §4 (release gate),
ADR-BOS-005, the Invoice Issue decision-closure analysis, the two completed
invoice-readiness audits (08.08.2026), current Bulgarian VAT law as
applicable in 2026 (see **Legal sources** below)

## Purpose and lifecycle

Invoice Draft is implemented and usable end to end (create, list, get,
line-edit). **Invoice Issue cannot begin** until every remaining
PROFESSIONAL REVIEW REQUIRED item below has a recorded, dated answer from a
qualified Bulgarian accountant — this is not an engineering gate, it is
already a named release gate (docs/12 §4: "accountant sign-off flag for any
release touching `commercial`") and several of these points carry real legal
risk if guessed instead of confirmed (docs/01 §7: "Invoice legal correctness
— mitigated by accountant review before release"). Items now marked
LAW-CONFIRMED do not need re-litigating — they need a professional read of
this document to confirm the citations and reasoning are sound, not a fresh
answer from scratch.

Since this document was opened, one prerequisite slice has landed: **Company
Legal Requisites management** (Owner-only `GET`/`PATCH
/api/v1/company/requisites`, tenant Settings → Фирма). It gives the tenant
Owner a real, allow-listed way to set `address`, `phone`, and
`vat_registered`. It does not by itself satisfy every seller-requisite
question below — see §3.

**This pass does not invent legal answers.** Every LAW-CONFIRMED conclusion
below cites the specific article it rests on. Where the research could not
reach a confident, well-sourced conclusion, the item stays PROFESSIONAL
REVIEW REQUIRED rather than being guessed. **This pass changes no code, no
schema, and no architecture** — it only researches, classifies, and
documents. Two genuine **contradictions between the current docs/architecture
and current law** were found (annual-reset numbering, and the
annul+reissue-only correction model) — both are called out explicitly below
and in the Freeze section; neither has been fixed, only flagged.

### Legal sources

Primary law: **ЗДДС** (Закон за данък върху добавената стойност — VAT Act),
**ППЗДДС** (Правилник за прилагане на ЗДДС — VAT Act implementing
regulation), **ЗСч** (Закон за счетоводството — Accountancy Act), **ДОПК**
(Данъчно-осигурителен процесуален кодекс — Tax and Social Insurance
Procedure Code), and the **Закон за въвеждане на еврото в Република
България** (Euro Introduction Act, "ЗВЕРБ" below). Access path: **NRA's own
official page** (nra.bg — "Фактуриране") was reached directly and used as a
primary source; it independently confirms the full чл. 114, ал. 1 mandatory
content list and the чл. 113 deadline used throughout this document. The
official consolidated statute text (lex.bg) returned an access error on
every attempt during this pass and could not be reached directly. Remaining
conclusions are grounded in **cross-checking multiple independent
professional Bulgarian accounting/tax publications (kik-info.com,
exlege.bg, and similar) and the KPMG summary of the 1.1.2026 ЗДДС
amendments**, none relied upon alone. This is a solid basis for planning
but **is not a substitute for a qualified accountant's or tax lawyer's
sign-off against the official consolidated text** before Issue ships —
that final read-through is exactly what the remaining PROFESSIONAL REVIEW
REQUIRED items ask for, and it is also good practice to have someone
re-verify the LAW-CONFIRMED citations against the current official text
directly on lex.bg or the State Gazette, since Bulgarian tax law amends
frequently (2026 alone introduced a small-enterprise VAT regime change
cited below). Secondary commentary was used only to corroborate or locate
citations, never as the sole basis for a LAW-CONFIRMED conclusion, and
never to override the primary-source material that was reachable.

Once every remaining PROFESSIONAL REVIEW REQUIRED row has a recorded
accountant answer, record it in the **Answer** column with the confirming
accountant's name and date. **When every such row is answered, this document
becomes the accountant sign-off record** the Invoice Issue slice cites
(docs/12 §4), and any frozen document it then requires amending (docs/01,
02, 08, 09) goes through the standard docs/07 change process in the same
change that implements Issue.

---

## Invoice V1 Decision Checklist (consolidated)

The original 26 items, each classified as exactly one of:

- **LAW-CONFIRMED** — the applicable law gives a sufficiently clear answer;
  cited below.
- **PRODUCT DECISION** — law permits alternatives or does not prescribe the
  behavior; RepairFlow chooses, bounded by the legal minimum stated.
- **PROFESSIONAL REVIEW REQUIRED** — materially interpretation-dependent,
  accounting-policy-specific, or high-risk enough that guessing would be
  irresponsible.
- **DEFERRED FROM V1** — legally relevant but intentionally out of scope for
  the first release; still needs a professional's confirmation that
  deferring is safe.

| # | Item | Classification | Basis / Note |
|---|---|---|---|
| N1 | Numbering continuity (annual reset vs. continuous) | **LAW-CONFIRMED** | Continuous, never reset by calendar year. ППЗДДС §1 below. **Contradicts current architecture** — see §1. |
| N2 | Number format (digits, leading zeros, prefix) | **LAW-CONFIRMED** (format) / **PRODUCT DECISION** (padding display) | 10-digit, Arabic numerals only, no letters. ЗДДС чл. 113/114, ППЗДДС чл. 78. |
| N3 | Numbering reset on VAT-registration status change | **LAW-CONFIRMED** | No reset — same continuous sequence rule as N1 applies regardless of registration status changes. |
| D1 | Tax event date, distinct field from issue date | **LAW-CONFIRMED** | Yes, required. ЗДДС чл. 114, ал. 1 (tax-event/advance-payment date is its own enumerated element). **Done** (migration 0018): `invoices.tax_event_date` (Date, nullable, read-only) — see §2. |
| D2 | How the tax event date is determined | **PRODUCT DECISION** (bounded by law) | Law defines *what* the tax event is (чл. 25 ЗДДС); RepairFlow decides *which order-timeline moment* maps to it. See §2. |
| T1 | Seller printed field set | **LAW-CONFIRMED** (core list) / **PROFESSIONAL REVIEW REQUIRED** (completeness sign-off) | Name, address, identification number are law-confirmed; final field-by-field sign-off still wanted. See §3. |
| B1 | Buyer field set — company (B2B) | **LAW-CONFIRMED** (core list) / **PROFESSIONAL REVIEW REQUIRED** (completeness sign-off) | Same shape as T1, buyer side. See §4. |
| B2 | Buyer field set — individual (B2C) | **PROFESSIONAL REVIEW REQUIRED** | Name/address are the base case; whether a national ID number is required depends on invoice-vs-receipt distinction. See §4. |
| R1 | Seller ЕИК/БУЛСТАТ required before Issue | **LAW-CONFIRMED** | Required — it *is* the "идентификационен номер" ЗДДС чл. 114 mandates. See §3. |
| R2 | Seller VAT number, conditional on `vat_registered` | **LAW-CONFIRMED** | Required only when VAT-registered; it is `"BG" + ЕИК`, not an independently issued number. ЗДДС чл. 94, ал. 2 / чл. 114. |
| R3 | Seller МОЛ required on the document | **LAW-CONFIRMED** | Not a чл. 114 mandatory element — optional business convenience. |
| R4 | Seller IBAN/bank details required | **LAW-CONFIRMED** | Not a чл. 114 mandatory element — optional business convenience. See §12. |
| R5 | Full Issue-time required-field list | **PRODUCT DECISION** (bounded by R1–R2) | Once R1/R2 are implemented, this is "which of the law-confirmed fields gate the Issue action" — a product completeness-check design, not a new legal question. |
| V7 | Is registered/not-registered a sufficient VAT-mode model | **PRODUCT DECISION** | Law recognizes more regimes (see 2026 SME regime, §6), but for a domestic repair shop the binary model is sufficient; special regimes are DEFERRED. |
| V1 | VAT rounding, per-line vs. total | **PROFESSIONAL REVIEW REQUIRED** | No unambiguous statutory algorithm found. See §6. |
| V2 | Tax calculation order (net → VAT → gross) | **LAW-CONFIRMED** | VAT is defined as a rate applied to данъчна основа (net); gross is derivative. ЗДДС чл. 26/чл. 67. |
| V3 | Meaning of a null `vat_rate` | **PRODUCT DECISION** (bounded by law) | Law distinguishes 0%-rated from not-charged (different legal bases) — RepairFlow decides how `NULL` vs an explicit rate encodes that. See §6. |
| T3/V4 | Exact wording for non-VAT-registered sellers | **LAW-CONFIRMED** (2026 rule) / **PRODUCT DECISION** (whether to print anyway) | From 1.1.2026, SME-regime non-registered sellers need **not** state a legal basis at all (new ЗДДС чл. 114, ал. 7, т. 1). Printing a plain-language note anyway is a product choice, not a legal necessity. |
| T4 | Payment method/reference line on the document | **PRODUCT DECISION** | Not a чл. 114 mandatory element. See §12. |
| T5 | Signatures required on the invoice | **LAW-CONFIRMED** | Not required — the preparer's-signature requirement was removed from ЗДДС чл. 114 effective 01.01.2009 (ДВ бр. 106/2008). |
| T6 | Footer content | **PRODUCT DECISION** | No legal minimum found. |
| T7 | Final template sign-off | **PRODUCT DECISION** (process gate) | Blocked only on the narrower B2 and V1 items now, not the whole template. |
| C1 | Annul+reissue legally sufficient, or credit/debit note required | **LAW-CONFIRMED** | Sufficient *only* for genuine documentation errors (ЗДДС чл. 116); **not** sufficient for a correctly-issued supply that later changes (ЗДДС чл. 115 requires a credit/debit note instead). **Contradicts current single-mechanism design** — see §7. |
| C2 | Correction-chain depth limit | **PRODUCT DECISION** | No statutory ceiling found on repeated annul+reissue of documentation errors. |
| V5 | Reverse charge — in scope for V1 | **DEFERRED FROM V1** | Not applicable to a domestic repair-shop fact pattern; safe to defer. |
| V6 | Advance/prepayment invoices — in scope for V1 | **DEFERRED FROM V1** | Legally distinct instrument with its own 5-day-from-receipt deadline (ЗДДС чл. 113, ал. 5) when triggered; safe to defer *if* the product doesn't currently create that trigger for undocumented deposits. See §9. |

**Result: 12 LAW-CONFIRMED · 8 PRODUCT DECISION · 4 PROFESSIONAL REVIEW
REQUIRED · 2 DEFERRED FROM V1 (26 total).** Four items (N2, T1, B1, T3/V4)
carry two classifications, one per sub-question; each is counted once above
under whichever classification is still blocking (PROFESSIONAL REVIEW
REQUIRED for T1/B1, LAW-CONFIRMED for N2/T3-V4 since their remaining part is
a bounded product choice, not an open question).

---

## 1. Invoice numbering

**N1 — LAW-CONFIRMED.** Bulgarian invoice numbering is **continuous for the
life of the registration and never resets on a calendar-year boundary**. The
10-digit number only restarts from `0000000001` after the entire range is
exhausted, and only after written notice to the competent NRA territorial
directorate (ППЗДДС numbering provisions, corroborated by multiple
independent professional sources and consistent with ЗДДС чл. 113/114's
"без пропуски и дублиране" — no gaps, no duplicates — requirement, which a
naive annual reset to the same starting digits would violate).

**This directly contradicts the current architecture if reused as-is.**
`service_orders.service.next_number()` (hardened this session per
ADR-BOS-005) keys `document_sequences` on `(company_id, kind, year)` and
resets `current` to 0 every calendar year *by construction* — correct and
harmless for order numbers (no legal significance), but if `kind="invoice"`
reuses the same function unmodified, two invoices in different years would
both be able to reach `0000000001`, which is a real compliance defect, not a
style choice. **This must be fixed before Issue is built** — most simply by
giving invoices their own non-year-scoped counter (e.g. `document_sequences`
row keyed on `(company_id, kind)` only, no `year`), not by reusing the
existing year-scoped key for `kind="invoice"`.

**N2 — LAW-CONFIRMED (format) / PRODUCT DECISION (display).** The number
must be exactly 10 digits, Arabic numerals only, no letters or prefix mixed
into the numeric value itself (ЗДДС чл. 113/114, ППЗДДС's numbering
provisions). `invoices.number` is already a plain integer — zero-padding to
10 digits is purely a display-format choice at render/print time, not a
schema change. Multiple independent, non-overlapping numbering *ranges* or
*series* are legally **permitted** (not required) — e.g. per branch — but
"the series does not participate in the invoice's unique identification":
the 10-digit number alone must be unique, a prefix cannot be used to
disambiguate two invoices sharing the same digits. **Recommended V1
decision:** one continuous series per company, zero-padded to 10 digits at
render time — the simplest option consistent with the law and with the
existing per-company `document_sequences` design (once N1's fix is applied).

**N3 — LAW-CONFIRMED.** No reset on a VAT-registration status change either
— same continuous-sequence rule as N1; a company's invoice numbering is a
property of the company's document history, not of its current VAT status.

---

## 2. Invoice dates

**D1 — LAW-CONFIRMED.** Yes: ЗДДС чл. 114, ал. 1 lists, as one of the
invoice's mandatory elements, "the date on which the tax event for the
supply occurred, **or** the date on which an advance payment was received"
— a field legally distinct from the invoice's own issue date (which is a
separate, also-mandatory element). **Done (migration 0018):**
`invoices.tax_event_date` (`Date`, nullable, no server default, no
backfill) — added as its own prerequisite slice, schema and read-only API
exposure only (`GET`/`POST`-detail responses include it; no request schema
accepts it — no code writes it yet). Unlike every other Etap-4 `invoices`
column, this one was **not** pre-provisioned by migration 0009.

**D2 — PRODUCT DECISION, bounded by law; not yet implemented.** ЗДДС чл. 25
defines the tax event itself as the supply of the goods/service (transfer
of ownership, or completion of the service) — for RepairFlow's repair-order
fact pattern, the natural candidate is the order's delivery moment
(`delivered_at` / warranty-return equivalent), not the invoice's own issue
date, which can legally follow the tax event by up to 5 days (ЗДДС чл. 113,
ал. 1: invoice must be issued no later than 5 days after the tax event, or
after receiving an advance payment). This remains a **recommendation for
the future Issue workflow**, not something the prerequisite slice
implements — no code today infers or sets `tax_event_date` from the order's
delivery date, current date, or any other source; every Draft's value stays
`NULL` until Issue exists. **Recommended V1 decision (unchanged):** default
`tax_event_date` to the order's delivery date at Issue time, editable by the
Owner at the moment of issuing (covers the diagnostic-fee-on-a-declined-order
case, which has no "delivery," and any other edge case) rather than trying
to auto-derive it from every possible order-terminal path.

---

## 3. Seller requisites

**T1 / R1 / R2 — LAW-CONFIRMED (what's required).** ЗДДС чл. 114, ал. 1
requires, for the supplier: name, address, and "идентификационен номер по
чл. 94, ал. 2" — which *is* the ЕИК/БУЛСТАТ for a non-VAT-registered
company, and *is* the ДДС-registration number (`"BG" + ЕИК`, not an
independently assigned value) when the company is VAT-registered (ЗДДС чл.
94, ал. 2). In plain terms: **name, address, and ЕИК/БУЛСТАТ are always
required; the VAT number is additionally required, and is derived from the
same ЕИК, only when `vat_registered` is true.**

- `Company.requisites.address` — **already collectible** (Company Legal
  Requisites slice).
- Legal name — **already available** (`Company.name`, always set, no gap).
- ЕИК/БУЛСТАТ — **collectible** (seller/buyer legal-requisites prerequisite
  slice). In the allow-list (`COMPANY_REQUISITE_KEYS = ("address", "phone",
  "eik")` in `identity/service.py`), with a Settings → Фирма field and a
  conservative structural validator (digits, 9 or 13 characters — see
  `shared_kernel/normalize.is_valid_eik`).
- VAT number — **not a distinct stored field**, and by design: it is fully
  derivable from ЕИК once ЕИК is collected and `vat_registered` is known
  (both now real fields) — just a `"BG" + eik` formatter, no independent
  storage needed.

**R3 (МОЛ) — LAW-CONFIRMED: not required.** МОЛ (materially responsible
person) does not appear among ЗДДС чл. 114's enumerated mandatory elements
in any source consulted. It is common business convenience, not a legal
requirement — safe to leave out of V1 entirely, or add later as a purely
optional field with no Issue-time gate depending on it.

**R4 (IBAN/bank details) — LAW-CONFIRMED: not required.** Also absent from
чл. 114's mandatory list. See §12 for the payment-details framing.

**R5 — PRODUCT DECISION, bounded by R1/R2.** Once ЕИК (and, when
`vat_registered`, the derived VAT number) exist as real fields, the
Issue-time completeness gate is simply "does the company have a name,
address, and ЕИК, plus (conditionally) `vat_registered`" — a product
implementation detail, not an open legal question anymore.

**PROFESSIONAL REVIEW REQUIRED (T1 completeness):** a final accountant
read-through confirming this reading of чл. 114's supplier-side list is
complete and current, since minor wording amendments do happen (2026's SME
regime change is a live example of the law moving under this exact article).

---

## 4. Buyer requisites

**B1 (company/B2B buyer) — LAW-CONFIRMED (core list), same shape as §3.**
When the recipient is itself a taxable person (a business), ЗДДС чл. 114
requires the same category of identifiers on the buyer side: name, address,
and identification number (ЕИК, plus VAT number when the buyer is itself
VAT-registered). **Schema/UI gap closed for name/address/ЕИК (seller/buyer
legal-requisites prerequisite slice):** `Customer.company_requisites` is now
a typed, allow-listed `CustomerCompanyRequisites` schema (`address`, `eik`;
`extra="forbid"`, `customers/router.py`) — replacing the previous fully-
unconstrained `dict[str, Any]` — and `Customer.is_company` is settable from
the intake create flow and editable in place from the customer profile
page's "Данни за фактуриране" section.

**Buyer VAT-number handling — OPEN, deferred to a future Issue-slice, not
frozen by this document.** Unlike R2 on the seller side (§3, explicitly
LAW-CONFIRMED and grounded in ЗДДС чл. 94, ал. 2 for the *reporting entity's
own* VAT-registration derivation), this document has never stated a
buyer-side equivalent. The `{address, eik}` contract intentionally omits a
stored buyer VAT-number field for this prerequisite slice — that scoping
choice was made by the implementer on the assumption that the same
"BG" + ЕИК derivation formula that's law-confirmed for a VAT-registered
entity's own number would extend to a VAT-registered buyer too, since it's
the same underlying legal fact about how BG VAT numbers are assigned,
independent of transaction role. That assumption itself has **not** been
accountant-confirmed here, and — more concretely blocking than the
derivation-formula question — there is still **no `Customer`-side
VAT-registration signal at all** (no `vat_registered`-equivalent field), so
the product has no way today to know *whether* a given company customer is
VAT-registered in the first place. **Consequence: `Invoice.buyer` snapshots
are not yet complete for a VAT-registered B2B recipient** — `{address, eik}`
is sufficient only for the currently frozen prerequisite scope (schema/UI
existence of `is_company`/`company_requisites`), not for a future Issue
workflow's completeness gate on VAT-registered buyers. Both the missing
buyer VAT-registration flag and confirmation of the derivation formula for
the buyer role need to be resolved — by product decision and/or
professional review — before that future Issue slice can build a correct
`Invoice.buyer` snapshot for this case.

**B2 (individual/B2C buyer) — PROFESSIONAL REVIEW REQUIRED.** This is the
most sensitive open item in the whole document, and deliberately **not**
resolved by assumption here, per your explicit instruction. Two genuinely
different Bulgarian legal tracks apply to a private walk-in customer, and
which one governs depends on a fact the product doesn't currently model:

1. **No invoice requested at all.** ЗДДС чл. 113, ал. 3, т. 1: when the
   recipient is a non-taxable individual, the supplier is **not** obligated
   to issue an invoice at all, unless the individual explicitly asks for
   one. RepairFlow's existing "invoices optional per order" design
   (docs/02) is **LAW-CONFIRMED correct** for this case — most walk-in
   repair customers who never ask for a "фактура" need nothing beyond the
   existing intake/delivery protocol and a cash/card payment record.
2. **A private individual explicitly requests a real VAT invoice.** Multiple
   independent sources (converging on ЗДДС чл. 114 read together with ЗСч
   чл. 6, ал. 1, т. 3, and ДОПК чл. 84 for the identifier itself) state that
   a proper "фактура" issued to an individual must carry that individual's
   national identification number — EGN for a Bulgarian citizen, or the
   ДОПК чл. 84 equivalent for a foreigner — as a mandatory requisite, and
   that a document missing it is not a valid tax invoice.

Point 2 is exactly the kind of conclusion this task told me not to invent:
it is well-sourced across several independent professional publications, but
I could not verify it against the primary consolidated ЗДДС text directly
(access was blocked during this research pass), the disclosed point-number
citation varied slightly between sources, and it has real privacy-by-design
consequences (`Customer` currently collects no national-ID field of any
kind, by design, and adding one is not a trivial "just add a column"
decision — it touches data-minimization posture, not just schema). **Flagged
PROFESSIONAL REVIEW REQUIRED, not treated as decided.** The practical
product question to put to the accountant: *does RepairFlow need to collect
a national ID number from a private customer, and if so, only at the
moment they explicitly request a real invoice (not at intake/order-creation
time for everyone)?*

---

## 5. Invoice line requirements

`InvoiceLine` today: `description`, `qty` (int), `unit_price`, `vat_rate`
(nullable), `source`, `sort`. Against ЗДДС чл. 114's line-level content
(description/type of goods or service, quantity, unit price excl. tax, tax
base, rate, VAT amount, and — if it differs from base+VAT — the amount
payable):

- description, quantity, unit price — **already present, LAW-CONFIRMED
  sufficient.**
- tax base, VAT rate, VAT amount, gross — **computable from existing
  columns** (`qty × unit_price` = base; `vat_rate` exists; VAT amount and
  gross are derived, not stored per line today, and don't need to be —
  see §6 on rounding for the one open question this raises).
- **unit of measure (мерна единица)** as a distinct, separately labeled
  field — **PROFESSIONAL REVIEW REQUIRED.** I could not find a clear
  statutory requirement for a *separate* unit field distinct from the
  description (Bulgarian invoices commonly fold the unit into the
  description text itself, e.g. "труд — 2 часа," "част — 1 бр.," which the
  existing free-text `description` already supports) — but I also could not
  confirm its absence is definitely fine. Recommend a direct question to
  the accountant rather than either assuming a new required field or
  assuming today's free-text approach is definitely enough.

---

## 6. VAT behavior

**Standard domestic scenario (VAT-registered seller) — LAW-CONFIRMED.**
Standard rate is 20% (ЗДДС чл. 66) — the correct rate for RepairFlow's
repair/labor/parts supplies, which are ordinary domestic services with no
reduced-rate category applicable. (Bulgaria also has a 9% reduced rate for
specific categories — accommodation, restaurant/catering, certain books —
confirmed by NRA's own guidance; noted for completeness only, since it does
not apply to repair-shop supplies and needs no support in V1.) Tax
calculation order is net → VAT → gross by definition: VAT is defined as the
rate applied to the данъчна основа (tax base/net amount, ЗДДС чл. 26), gross
is base + VAT — there is no alternative order to choose between; this part
of V2 is not a product decision at all, it's how VAT is defined.

**V1 (rounding, per-line vs. total) — PROFESSIONAL REVIEW REQUIRED.** No
unambiguous statutory algorithm was found specifying whether VAT must be
computed and rounded per invoice line then summed, or computed once on the
invoice's aggregate net total. This is exactly the kind of
implementation-level accounting-policy question the task asked to flag
rather than resolve by assumption — different Bulgarian accounting software
packages are not consistent with each other here in practice, which is
itself evidence there's no single mandated algorithm. **Recommended simplest
safe V1 decision (not a legal conclusion):** round once, on the invoice
total, to 2 decimal places (`Numeric(10,2)`, matching the existing
`net`/`vat`/`gross` column precision) — simpler to implement and audit than
per-line rounding-then-summing, and defensible as a common, non-aggressive
choice, but this should be the specific thing put in front of the
accountant, not assumed settled by this document.

**V3 (null `vat_rate`) — PRODUCT DECISION, bounded by law.** Law
distinguishes two genuinely different things that a "no VAT shown" line
could mean: a statutorily **0%-rated** supply (needs its own legal-basis
citation on the document per ЗДДС чл. 114, ал. 1 — e.g. exports,
intra-Community supplies) versus VAT simply **not charged** because the
*seller* isn't VAT-registered (a different legal basis, T3/V4 below).
Neither case is a realistic V1 scenario for a domestic repair shop's
services (0%-rating applies to specific cross-border/export fact patterns,
not domestic repairs) — **recommend**: `vat_rate = NULL` continues to mean
"seller not VAT-registered, no VAT applicable" (the only case V1 needs),
and true 0%-rated-supply support is DEFERRED FROM V1 alongside reverse
charge (V5) rather than half-modeled through the same nullable column.

**Can `Invoice.vat_mode` represent this distinction correctly? Yes, as a
structural convention, once that convention is documented.**
`vat_mode` (invoice-level: `registered`/`not_registered`) and `vat_rate`
(line-level: nullable) are orthogonal columns, which is actually the right
shape: a `vat_mode="not_registered"` invoice would have every line's
`vat_rate` at `NULL` (not charged, no basis text needed per T3/V4); a
future `vat_mode="registered"` invoice with a genuinely 0%-rated line (were
that ever built) would use an explicit `vat_rate = 0.00`, not `NULL` — the
two states are distinguishable in the schema as long as the product
convention "`NULL` means not-charged, `0.00` means zero-rated" is followed
consistently and documented, not just implied. No schema change needed for
V1; this is a documentation/convention gap, not a structural one.

**T3/V4 (non-VAT-registered wording) — LAW-CONFIRMED, and the law itself
changed for 2026.** As of 1.1.2026, a new small-enterprise ("SME") VAT
regime took effect (transposing EU Directive 2020/285, with a registration
threshold around €51,130/year). Under the new ЗДДС чл. 114, ал. 7, т. 1
(2026 amendment), a person applying this regime **need not state any legal
basis for not charging VAT at all** — a real relaxation from the older rule
(which required citing a specific article, e.g. чл. 113, ал. 9, as the
"basis for non-charging"). **Recommended V1 decision:** print no mandatory
legal-basis text for non-VAT-registered sellers (matches the current 2026
rule), optionally with a short plain-Bulgarian courtesy note like
"ДДС не се начислява" for readability — a product/UX choice, not a legal
requirement, and should not be worded as if it were a citation of a specific
article unless an accountant confirms the seller doesn't in fact need the
older-style basis text for some reason specific to their situation.

**V7 (VAT-mode model) — PRODUCT DECISION.** The binary
`registered`/`not_registered` `vat_mode` already in the schema is
sufficient for RepairFlow's actual customer base (small domestic repair
shops); other regimes (group registration, distance-selling thresholds,
the new SME regime's own nuances) are realistically DEFERRED — no
architectural reason to model them until a real tenant needs one.

**V5 (reverse charge) — DEFERRED FROM V1.** Never arises for a domestic
repair shop's ordinary in-country services; safe to defer, consistent with
the proposed V1 scope's own "domestic standard final invoices only"
framing.

---

## 7. Corrections after issue

The task's A/B/C distinction is **exactly right, and the current docs
under-specify it** — this is the second contradiction this pass surfaces.

- **A. Incorrectly prepared invoice** (a documentation mistake — wrong
  amount typed, wrong customer selected, etc.; the underlying supply itself
  was never actually what the document says). **Legal mechanism: ЗДДС чл.
  116** — cancel (anul) the erroneous document and issue a new, correct one.
  **This is the only scenario "annul + reissue" is legally sufficient
  for.**
- **B. Subsequent reduction of a correctly-issued supply** (goods returned,
  a price reduction agreed after the fact, part of the work cancelled after
  a correct invoice was already issued for it). **Legal mechanism: ЗДДС чл.
  115 — a credit note (кредитно известие) is required.** The original
  invoice was correct when issued; it is not annulled, it is referenced by
  a separate corrective document.
- **C. Subsequent increase of a correctly-issued supply** (additional
  agreed work, a price increase after the fact). **Legal mechanism: ЗДДС
  чл. 115 — a debit note (дебитно известие) is required.** Same shape as B,
  opposite direction.

**C1 — LAW-CONFIRMED: annul + reissue is legally sufficient only for case
A.** Cases B and C are a **structurally different instrument** under the
law, not a wording variant of the same thing. **This is a real contradiction
with the current design**, not just an unanswered question:
`Invoice.annuls_invoice_id`/`annul_reason` and docs/02's "Duplicate/wrong
invoice → Annul + reissue; gapless numbering preserved" line only speak to
case A. Nothing in the current schema represents a credit or debit note (no
`kind`/`type` distinguishing a corrective document that *references* an
issued invoice from one that *replaces* it), and the proposed V1 scope's own
caution — "the model must not incorrectly use annul+reissue for situations
where the law requires a note" — is the right instinct and needs to be
enforced by product copy/scope, not just intention: **V1's Annul action, if
built, must be restricted (by wording and, ideally, by a required
"is this actually a mistake, or did the real supply change?" prompt) to
case A only, with cases B/C explicitly out of scope until credit/debit notes
exist** (not merely discouraged in a tooltip).

**C2 (correction-chain depth) — PRODUCT DECISION.** No statutory ceiling
found on how many times an erroneous-invoice cycle (case A) can repeat;
`annuls_invoice_id` as a single-predecessor link is fine for V1, since
each annul+reissue is independently a case-A correction, not a chain that
needs multi-hop traversal for any legal reason found.

**Credit/debit notes themselves — confirmed safe to defer, with one
constraint on the numbering design (see §1):** ППЗДДС numbering guidance is
explicit that invoices and known (known = известия, i.e. credit/debit
notes) **share one continuous numbering sequence** — "номерирането... не
зависи от вида на документа." When credit/debit notes are eventually built,
they must **not** get an independent `document_sequences` counter; they must
draw from the same per-company invoice sequence. Worth designing §1's fix
with this in mind now, even though nothing needs building yet.

---

## 8. Immutability

**LAW-CONFIRMED.** ЗДДС чл. 116 itself establishes that correcting an
already-issued document is never done by editing it in place — only by
cancellation-and-reissue (case A) or a credit/debit note (cases B/C). This
directly confirms the frozen invariant already stated in docs/01
("issued invoices are never edited — legal requirement") and the existing
`InvoiceLine`/`replace_lines` guard's design intent (`if invoice.status !=
"draft": raise ...not_draft`) is the right shape — the guard already exists
in the service layer, it is simply unreachable today because no `issue()`
endpoint exists yet to ever set `status="issued"`. No contradiction here;
this item needed confirmation, not correction.

---

## 9. Advance payments

**V6 — DEFERRED FROM V1, consistent with the existing accepted project
decision** (docs/ACCOUNTANT_REVIEW.md's own prior framing, carried forward)
**and legally sound as long as one condition holds.** ЗДДС чл. 113, ал. 1
and ал. 5: an invoice must be issued no later than 5 days after receiving an
advance payment, the same deadline rule that applies to the tax event
itself — meaning an "авансова фактура" is a real, distinct legal
obligation, not an optional nicety, **when it is triggered**. It is
triggered for a VAT-registered supplier receiving an advance from another
taxable person (a business), or when an individual explicitly requests
documentation of the deposit. **PROFESSIONAL REVIEW REQUIRED, narrowly:**
confirm that RepairFlow's current deposit-taking flow (a `Payment` recorded
against an order, `is_refund=false`, no `invoice_id` set — see
`DeliveryDialog`/`add_payment`) does not, for the typical case, itself
create an obligation the product is silently failing to meet today, i.e.
that deferring advance-invoice *support* is safe because most repair-shop
deposits fall under the "individual, no invoice requested" exemption
(§4, B2 point 1) rather than a business-customer advance that would need
one within 5 days.

**Architecture check requested by the task: already satisfied, no gap.**
`Invoice.order_id` is a plain foreign key with no uniqueness constraint —
multiple `Invoice` rows per `ServiceOrder` are already structurally possible
today (confirmed by reading the model directly), matching docs/01's own
"ServiceOrder 1──* Invoice" cardinality. No schema change is needed to keep
this door open for a future advance-invoice slice.

---

## 10. Currency / EUR

**LAW-CONFIRMED.** Bulgaria adopted the euro on 1 January 2026 (fixed rate
1 EUR = 1.95583 BGN). From that date, invoices are issued **exclusively in
EUR** — the Euro Introduction Act explicitly **exempts** invoices issued
under ЗДДС чл. 112, ал. 1 from the dual BGN/EUR display requirement that
applies to consumer-facing prices (ЗВЕРБ чл. 15, ал. 3, т. 5). **No
dual-currency display is required on invoices.** `Invoice.currency`
already defaults to `"EUR"` — the schema already matches the law; no gap,
no change needed.

---

## 11. Electronic / PDF invoices

**LAW-CONFIRMED (acceptability).** Electronic invoices are legally
acceptable in Bulgaria; the preparer's-signature requirement was removed
from ЗДДС чл. 114 back in 2009 (same citation as T5), so a generated,
unsigned PDF is not disqualified on that basis. The law's actual condition
is that the issuer must be able to ensure **authenticity of origin,
integrity of content, and legibility**, achievable through business
controls (a "reliable audit trail"), not necessarily a cryptographic
signature.

**PROFESSIONAL REVIEW REQUIRED (control adequacy).** Whether RepairFlow's
planned implementation — server-generated PDF, `invoices` rows immutable
once `status="issued"`, `pdf_storage_key` pointing at a stored artifact —
constitutes an adequate "reliable audit trail" is a controls-adequacy
judgment the law states as a goal without prescribing the specific
technical means; worth a specific confirmation once the PDF-generation
design exists, not a blocking question for the schema/product-scope work
happening now.

**Stamp/seal:** not found as a legal requirement anywhere in the sources
consulted, consistent with the removal of even the signature requirement in
2009 — treated as LAW-CONFIRMED not required, same basis as T5.

---

## 12. Payment details

**LAW-CONFIRMED: none of payment method, paid/unpaid status, or IBAN/bank
information appear among ЗДДС чл. 114's mandatory invoice elements.** All
three are product conveniences, not legal requisites:

- **Payment method (T4)** — PRODUCT DECISION. Printing it is optional;
  RepairFlow already tracks it operationally via `Payment.method`, never
  needs to duplicate it onto the invoice document itself for V1.
- **Paid/unpaid status (PAY1, new)** — PRODUCT DECISION, and the existing
  architecture already gets this right: `Payment` records against an order
  (optionally an invoice) are the source of truth; an invoice's own "amount
  due" is properly a derived view, not a stored status field on `Invoice`
  itself. No gap.
- **IBAN/bank details (R4)** — PRODUCT DECISION, same as §3: common
  convenience for the buyer to know how to pay, never a legal requisite.
  Safe to leave out of V1's printed template and out of the seller
  requisites allow-list entirely, unless the product wants it purely for
  display convenience later.

---

## RepairFlow Invoice V1 Freeze

### 1. LAW-CONFIRMED

| Rule | Legal source/article | RepairFlow consequence |
|---|---|---|
| Invoice numbering is continuous for the life of the company's registration; never reset on a calendar-year boundary. | ППЗДДС numbering provisions; ЗДДС чл. 113/чл. 114 (no gaps, no duplicates); NRA official guidance (nra.bg). | **Done:** `next_invoice_number()` allocates from a fixed, non-year-scoped key (`INVOICE_SEQUENCE_EPOCH`); `next_order_number()` keeps the original year-scoped behavior unchanged. §1. |
| Invoice number is exactly 10 digits, Arabic numerals only, no letters. | ЗДДС чл. 113/114; ППЗДДС чл. 78; NRA official guidance. | `Invoice.number` (plain `int`) is already the right shape; zero-padding is a render-time format only. §1. |
| A tax-event date (or, for an advance, the payment-received date) is its own mandatory invoice element, distinct from the issue date. | ЗДДС чл. 114, ал. 1. | **Done** (migration 0018): `invoices.tax_event_date` (Date, nullable), exposed read-only in `GET /invoices/{id}`. Populating it is still a future Issue-workflow task. §2. |
| Seller name, address, and ЕИК/БУЛСТАТ are always required; the VAT number is required only when the seller is VAT-registered, and is derived from the ЕИК (`"BG" + EIK`), not independently issued. | ЗДДС чл. 114, ал. 1; чл. 94, ал. 2. | ЕИК needs a new allow-listed `Company.requisites` key + UI field; the VAT number likely needs no stored field of its own. §3. |
| МОЛ is not a mandatory invoice element. | ЗДДС чл. 114, ал. 1 (not enumerated). | Safe to omit from V1 entirely; no Issue-time gate depends on it. §3. |
| Phone, email, and IBAN/bank details are not mandatory invoice elements, for either party. | ЗДДС чл. 114, ал. 1 (not enumerated). | Safe to keep off the printed template and out of the required-field gate. §3, §4, §12. |
| Tax calculation order is net → VAT → gross; this is definitional, not a choice. | ЗДДС чл. 26 (tax base), чл. 66 (rate applied to the base). | Totals-freeze code at Issue must compute in this order; no alternative to pick between. §6. |
| From 1.1.2026, a non-VAT-registered seller under the small-enterprise regime need not state any legal basis for not charging VAT. | ЗДДС чл. 114, ал. 7, т. 1 (2026 amendment, transposing EU Directive 2020/285). | No mandatory legal-basis text on the V1 template for non-registered sellers — a real relaxation from the pre-2026 "cite the article" rule. §6. |
| Signatures (and, by the same basis, stamps) are not required on the invoice. | ЗДДС чл. 114 — preparer's-signature requirement removed effective 01.01.2009 (ДВ бр. 106/2008). | The generated PDF needs no signature/stamp field or line. §3, §11. |
| Annul + reissue is legally sufficient only for a genuinely erroneous document (case A); a correctly-issued supply that later decreases needs a credit note, and one that later increases needs a debit note — a structurally different instrument, not a wording variant. | ЗДДС чл. 116 (case A, cancel + reissue); чл. 115 (cases B/C, credit/debit note). | `Invoice.annuls_invoice_id`/`annul_reason` and any Annul action must be scoped to case A only; docs/01 and docs/02 must be corrected to state this explicitly. §7. |
| An already-issued invoice may never be corrected by editing it in place — only by case-A cancel+reissue or a case-B/C note. | ЗДДС чл. 116 (the same provision that establishes cancel+reissue as the correction mechanism, not in-place edit). | Confirms the existing `replace_lines` `status != "draft"` guard's design is correct; it is simply unreachable today since no `issue()` endpoint exists yet. §8. |
| Invoices issued in Bulgaria from 1 January 2026 are exclusively in EUR, with no dual BGN/EUR display requirement. | Закон за въвеждане на еврото (Euro Introduction Act) чл. 15, ал. 3, т. 5 — explicit exemption for documents under ЗДДС чл. 112, ал. 1. | `Invoice.currency` already defaults to `"EUR"` — no schema or product change needed. §10. |
| Electronic (PDF) invoices are legally acceptable; the law's condition is authenticity of origin, integrity of content, and legibility, not a specific technical mechanism. | Same 2009 signature-removal basis as above; general e-invoice authenticity/integrity principle corroborated across multiple sources. | A server-generated, unsigned PDF is not disqualified in principle. §11. |
| Payment method, paid/unpaid status, and IBAN/bank information are not mandatory invoice elements. | ЗДДС чл. 114, ал. 1 (not enumerated). | All three can stay purely operational (`Payment` records), never printed on the V1 template, with no compliance gap. §12. |
| Credit/debit notes, once built, must draw from the same continuous numbering sequence as invoices — not an independent counter. | ППЗДДС numbering guidance — numbering "does not depend on the type of document" for invoices and known (известия) alike. | The §1 numbering-key fix should be designed with this in mind now, even though nothing needs building yet. §7. |

### 2. PRODUCT DECISIONS

| Legal freedom/boundary | Chosen V1 behavior | Reason |
|---|---|---|
| Law permits multiple independent numbering series/ranges; does not require more than one. | One continuous invoice-number series per company. | Simplest option consistent with the law and the existing per-company `document_sequences` design, once its year-scoping is fixed. §1. |
| Law defines what the tax event is (чл. 25 ЗДДС) but not which order-lifecycle moment a repair shop should map it to. | `tax_event_date` defaults to the order's delivery date, editable by the Owner at Issue time. | Covers the normal delivery case and edge cases (e.g. a diagnostic fee on a declined order, which has no delivery) without over-automating. §2. |
| Law distinguishes 0%-rated supplies from "not charged because unregistered" (different legal bases) but does not require both to be modeled in a first release. | `vat_rate = NULL` means "seller not VAT-registered"; a future explicit `vat_rate = 0.00` would mean genuinely zero-rated, once that scenario is ever built. | Neither 0%-rating nor reverse charge is a realistic domestic-repair-shop fact pattern; avoids half-modeling a case V1 doesn't need. §6. |
| Law permits (per the 2026 amendment) omitting legal-basis text for non-registered sellers, but does not forbid printing a plain-language note. | No mandatory legal-basis text; an optional short courtesy note such as "ДДС не се начислява" for readability. | Matches the current 2026 rule exactly; a courtesy note is a UX choice, not a citation of a specific article that might not apply. §6. |
| Law does not require payment method, IBAN/bank details, or a footer to appear on the document. | All three left off the V1 printed template. | They are operational/business data, not document content; nothing is lost by keeping them out of the PDF. §3, §12. |
| The binary `registered`/`not_registered` VAT-mode model is legally incomplete (more regimes exist) but law does not require the product to support every regime immediately. | Binary model kept for V1; other regimes (group registration, distance-selling thresholds, the SME regime's own nuances) deferred. | Matches RepairFlow's actual customer base (small domestic repair shops); no real tenant need for more today. §6. |
| Law sets no ceiling on how many times a case-A (erroneous-invoice) cycle may repeat. | `annuls_invoice_id` stays a single-predecessor link. | Each annul+reissue is independently a case-A correction; no chain-traversal need found. §7. |
| Law requires *an* Issue-time completeness check (requisites must exist) but not its specific implementation shape. | Gate on: company has name, address, ЕИК, and (conditionally) a VAT number derived from `vat_registered`. | Directly follows once R1/R2's law-confirmed fields exist as real data; a product design detail, not an open legal question. §3. |
| Law does not require a stored "paid/unpaid" status on the invoice itself. | Amount due stays a derived view from `Payment` records against the order/invoice, never a stored `Invoice` field. | Matches the existing architecture already; avoids a second source of truth for money already tracked by `Payment`. §12. |

### 3. PROFESSIONAL REVIEW REQUIRED

| What must be confirmed | Why | Should implementation wait for it? |
|---|---|---|
| Final completeness sign-off on the §3/§4 reading of ЗДДС чл. 114's supplier/recipient field list. | The core substance (name, address, ЕИК, conditional VAT number) is already law-confirmed above; чл. 114 amends periodically (2026's SME change is a live example), so a fresh amendment could narrow or widen the list. | **No** — this is a courtesy final read-through of an already-implementable list, not a blocker for building the ЕИК field/UI or the seller-side Issue gate. |
| VAT rounding: per-line computation-then-sum, or compute once on the invoice total. | No unambiguous statutory algorithm was found; Bulgarian accounting software packages are not consistent with each other in practice, itself evidence there is no single mandated method. | **Yes, for the Issue/totals-freeze code specifically** — this directly determines what gets written to `net`/`vat`/`gross`. Does not need to block the numbering fix, the migration, or the requisites UI work, which are all independent of this answer. §6. |
| Whether a private (B2C) customer who explicitly requests a real invoice must supply a national ID number (EGN, or the ДОПК чл. 84 equivalent for a foreigner), and if so, collected only at that moment rather than by default. | The most sensitive open item in this document: well-sourced across independent professional publications, but not verified against the primary consolidated ЗДДС text directly (blocked during this pass), with real data-minimization consequences — `Customer` today collects no national-ID field of any kind, by design. | **Yes, before building any B2C invoice-issue UI** that would need to collect it — but it does **not** block the B2B UI surface (§4) or any of the schema/numbering prerequisite work, since the B2C case is a narrower slice of the eventual Issue feature. |
| Whether the free-text `InvoiceLine.description` (folding the unit into the text, e.g. "труд — 2 часа") is a sufficient representation of "unit of measure," or a distinct field is expected. | No clear statutory requirement for a *separate* unit field was found, but its absence also couldn't be confirmed as definitely fine. | **No** — low-risk either way; can be resolved alongside the rounding/template work without blocking the schema/numbering prerequisites. §5. |
| That RepairFlow's current deposit-taking flow (a `Payment` with no `invoice_id`, recorded via `DeliveryDialog`/`add_payment`) does not already create an unmet 5-day advance-invoice obligation for a business-customer deposit, even while advance-invoice *support* stays deferred. | ЗДДС чл. 113, ал. 1/ал. 5 make an advance-payment invoice a real, distinct obligation *when triggered* (a taxable-person recipient, or an individual who asks) — deferring the feature is only safe if the trigger doesn't already occur silently today. | **No** for the prerequisite schema/numbering work — **yes** before treating "advance invoices deferred" as fully risk-free in the accountant sign-off record. §9. |
| Whether the planned PDF-generation implementation (server-rendered, `invoices` immutable once issued, `pdf_storage_key` pointing at a stored artifact) constitutes an adequate "reliable audit trail" for authenticity/integrity purposes. | The law states the goal (authenticity, integrity, legibility) without prescribing the specific technical means — a controls-adequacy judgment, not a pure legal question. | **No** for schema/numbering work — **yes** once the actual PDF-generation design exists and can be evaluated concretely. §11. |

### 4. DEFERRED FROM V1

| Scenario | Confirmation that the architecture stays extensible |
|---|---|
| Advance/prepayment invoices (авансови фактури). | **Already extensible, no gap:** `Invoice.order_id` is a plain foreign key with no uniqueness constraint — multiple `Invoice` rows per `ServiceOrder` are already structurally possible today, matching docs/01's own "ServiceOrder 1──* Invoice" cardinality. The architecture must not assume, and today does not assume, one order = exactly one invoice forever. §9, §11 of the task's research list. |
| Reverse charge. | Not a realistic domestic-repair-shop fact pattern; no architecture accommodation needed beyond what already exists (`vat_mode`/`vat_rate` are generic enough to extend later if a tenant ever needs it). §6. |
| Cross-border / other special VAT regimes (group registration, distance-selling thresholds, the SME regime's own nuances beyond the basic wording relaxation). | Same as above — `vat_mode`'s binary model would need extending, not replacing, if this is ever needed; no V1 blocker. §6. |
| Credit/debit note implementation. | **Constrained, not just deferred:** whenever built, credit/debit notes must share the *same* invoice numbering sequence (per the numbering rule above), and the current `annuls_invoice_id`/`annul_reason` mechanism must **not** be repurposed for them — they need their own document representation. The V1 Annul action must be scoped, by product copy, to case-A documentation errors only, so it is never presented as a substitute for a case-B/C note the law actually requires. §7. |
| Payment-to-invoice reconciliation (linking specific `Payment` rows to a specific issued `Invoice` beyond the order level). | `Payment.invoice_id` already exists as a nullable FK — the column is already there, unused; no schema gap, purely a later feature-completeness item. May follow Issue/PDF. §12. |
| True 0%-rated supplies (as opposed to "not charged because unregistered"). | Already representable via the `vat_mode`/`vat_rate` convention documented in §6 (explicit `0.00` vs. `NULL`) once that convention is written down; no schema change needed when this is eventually built. §6. |

---

## Current Implementation Gap Matrix

Frozen V1 specification above, compared field-by-field against the current
repository. Classification is exactly one of: **already sufficient** · **code
plumbing required** (service/router-layer logic, no new column) ·
**frontend/write surface required** (a UI screen doesn't exist) ·
**migration required** (a real `ALTER TABLE`) · **documentation semantics
change required** (the column is fine, what it's allowed to mean needs
writing down) · **deferred** (intentionally out of V1 scope).

| Field | Classification | Note |
|---|---|---|
| `Invoice.number` | **Already sufficient** | Plain `int` matches the 10-digit numeric requirement; zero-padding is a render-time format. Its *allocation logic* is a separate gap — see `document_sequences` below. |
| `Invoice.issued_at` | **Already sufficient** | Confirmed correct semantics (issue timestamp only), no overlap with tax-event date. |
| `invoices.tax_event_date` | **Done (prerequisite slice landed)** | Migration 0018 added it: `Date`, nullable, no server default, no backfill — not provisioned by migration 0009, unlike every other Etap-4 `invoices` column. Model field + read-only `GET`/`POST`-detail exposure in `commercial/models.py`/`router.py`; no write path anywhere. §2. |
| `Invoice.seller` | **Already sufficient (schema)** | Correct JSONB snapshot shape; populating it at Issue depends on `Company.requisites`'s gap below, not on this column. |
| `Invoice.buyer` | **Already sufficient (schema)** | Same — depends on `Customer.company_requisites`/`is_company`'s (larger) gap below. |
| `Invoice.vat_mode` | **Already sufficient** | Binary `registered`/`not_registered` matches the V1 product decision; no change needed. |
| `Invoice.net` | **Already sufficient (schema) / documentation semantics change required (algorithm)** | `Numeric(10,2)` is the right shape; the rounding algorithm that populates it is the open V1 professional-review item (§6), not a column problem. |
| `Invoice.vat` | **Already sufficient (schema) / documentation semantics change required (algorithm)** | Same as `net`. |
| `Invoice.gross` | **Already sufficient (schema) / documentation semantics change required (algorithm)** | Same as `net`. |
| `Invoice.annuls_invoice_id` | **Documentation semantics change required** | Structurally fine for its actual scope; docs/01 and docs/02 must be corrected to state it covers case A only, not cases B/C. §7. |
| `Invoice.annul_reason` | **Documentation semantics change required** | Same correction as `annuls_invoice_id` — a case-A-only reason field, not a general correction-reason field. §7. |
| `InvoiceLine.description` | **Already sufficient** | Matches ЗДДС чл. 114's line-level description/type requirement. §5. |
| `InvoiceLine.qty` | **Already sufficient** | Matches the quantity requirement. §5. |
| `InvoiceLine.unit_price` | **Already sufficient** | Matches the unit-price requirement. §5. |
| `InvoiceLine.vat_rate` | **Already sufficient (schema) / documentation semantics change required (convention)** | Nullable `Numeric(5,2)` is the right shape; the `NULL` = not-charged vs. `0.00` = zero-rated convention (§6) needs to be written down, not just assumed by whoever writes the Issue code. |
| *(unit of measure)* | **Deferred** | Not confirmed as a real gap — flagged PROFESSIONAL REVIEW REQUIRED (§5), not yet classified as needing schema/code work. |
| `Company.name` | **Already sufficient** | Real, always-set legal/business name; no gap. |
| `Company.requisites` | **Done (prerequisite slice landed)** | `address`/`phone`/`eik` are collectible (`COMPANY_REQUISITE_KEYS` in `identity/service.py`, `eik` allow-listed and structurally validated in `identity/router.py`) with a Settings → Фирма field. No separate VAT-number field — always `"BG" + eik` once `vat_registered` is true (R2). |
| `Company.vat_registered` | **Already sufficient** | Already collectible via the landed Company Legal Requisites slice — no further gap. |
| `Customer.name` | **Already sufficient** | Real, UI-editable field; no gap. |
| `Customer.is_company` | **Done (prerequisite slice landed)** | Settable from the intake create flow and editable in place from the customer profile's "Данни за фактуриране" section. §4. |
| `Customer.company_requisites` | **Done for name/address/ЕИК (prerequisite slice landed); buyer VAT-number handling still OPEN** | Replaced the unconstrained `dict[str, Any]` with a typed, allow-listed `CustomerCompanyRequisites` schema (`address`, `eik` only, `extra="forbid"`) in `customers/router.py` — the same allow-list-contract treatment `Company.requisites` already had. No stored buyer VAT-number field — but unlike the seller side (R2), this document never froze that omission for buyers; it's an implementer scoping choice pending confirmation. `Invoice.buyer` is not yet complete for a VAT-registered B2B buyer: no `Customer`-side VAT-registration signal exists either. §4. |
| `document_sequences` | **Done (prerequisite slice landed)** | The compliance defect described in §1 is fixed, without a migration: `service_orders.service` now exposes `allocate_sequence()` (generic atomic counter, no formatting), `next_order_number()` (unchanged year-scoped order behavior), and `next_invoice_number()` (continuous, 10-digit zero-padded, keyed on the new `INVOICE_SEQUENCE_EPOCH = 0` constant instead of a bare inline `0`). `year=0` for `kind="invoice"` is documented in code as a fixed series/epoch marker, never a calendar year, and is only ever referenced through that one named constant — see `service_orders/service.py`. |

**Documentation decisions that must change** once this pass is accepted:
docs/01 (Invoice attributes: add tax-event date; correction section: split
case A from B/C), docs/02 (§11's "Duplicate/wrong invoice → Annul + reissue"
line needs the B/C distinction added, not replaced), docs/08 (add
`tax_event_date` to the frozen `invoices` column list; document the
numbering-key fix and the `vat_rate` NULL/0.00 convention), ADR-BOS-005 (its
"risk" section already flagged the concurrency race, now hardened — it
should also flag the year-scoping issue found here, since it inherits
`service_orders.next_number()`'s shape).

---

## After this document is complete

1. Every remaining PROFESSIONAL REVIEW REQUIRED row has a recorded answer,
   confirming accountant name, and date.
2. ~~The numbering fix (§1) is applied~~ — **done**: `next_invoice_number()`
   allocates from a non-year-scoped key (`INVOICE_SEQUENCE_EPOCH`);
   `next_order_number()` is unchanged. Landed ahead of Issue itself, as a
   standalone prerequisite slice with its own tests.
3. ~~A real migration adds `invoices.tax_event_date`~~ — **done** (migration
   0018): nullable `Date` column, model field, and read-only `GET`/POST-
   detail exposure. Landed as its own prerequisite slice; still `NULL` for
   every row until a future Issue workflow populates it — D2's "which
   order-timeline moment" question remains open.
4. ~~The seller ЕИК field (§3) extends the existing Company Legal Requisites
   allow-list~~ — **done**: `eik` is in `COMPANY_REQUISITE_KEYS`
   (`identity/service.py`) with a Settings → Фирма field; still needs
   wiring into the Issue-time completeness check once Issue itself exists.
5. ~~The buyer identifiers (§4) become a new Customer UI surface~~ —
   **done for B1's name/address/ЕИК** (company buyer): `is_company`/
   `company_requisites` are settable from the intake create flow and
   editable from the customer profile page. **Still open:** B1's buyer
   VAT-number handling (no stored field, no `Customer`-side VAT-registration
   signal — see §4) needs its own product decision/professional review
   before a future Issue slice can build `Invoice.buyer` correctly for a
   VAT-registered B2B buyer. B2 (individual/B2C buyer) remains gated on its
   own professional-review answer — untouched by this slice.
6. The correction mechanism (§7) — Annul action copy and scope — is built
   to explicitly cover case A only; credit/debit notes are a distinct,
   later slice, not retrofitted onto `annuls_invoice_id`.
7. The rounding algorithm (§6, V1) and the B2/unit-of-measure/advance-payment
   professional-review answers feed the totals-freeze and template code.
8. This document is cited from the Invoice Issue implementation slice as
   its accountant sign-off record (docs/12 §4 release gate).
