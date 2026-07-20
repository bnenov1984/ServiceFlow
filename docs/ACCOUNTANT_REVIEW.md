# Accountant Review — Invoice Issue

Status: **Pending — questions awaiting official accountant answers.** None of
the questions below has been answered yet. · Opened: 20.07.2026 · Source:
docs/00 §Q2, docs/01 §7, docs/02 §11/§13, docs/12 §4 (release gate), the
Invoice Issue decision-closure analysis

## Purpose and lifecycle

Invoice Draft is implemented and usable end to end. **Invoice Issue cannot
begin** until every question below has a recorded, dated answer from a
qualified Bulgarian accountant — this is not an engineering gate, it is
already a named release gate (docs/12 §4: "accountant sign-off flag for any
release touching `commercial`") and several of these questions carry real
legal risk if guessed instead of confirmed (docs/01 §7: "Invoice legal
correctness — mitigated by accountant review before release").

**Do not answer these from general knowledge or assumption.** Each question
exists because the authoritative product documents explicitly defer it
(cited per section below) — inventing an answer here would be exactly the
mistake docs/01 §7 and docs/12 §4 exist to prevent.

Once a question is answered, record it in the **Answer** column with the
confirming accountant's name and the date. **When every question in this
document has a recorded answer, it stops being a pending checklist and
becomes an authoritative project document** — the Invoice Issue
implementation slice cites it directly, and any frozen document it then
requires amending (docs/01, 02, 08, 09) goes through the standard docs/07
change process (written rationale → impact assessment → PO approval →
same-commit update) in the same change that implements Issue.

---

## 1. Invoice numbering

Frozen today: per-company scope, gapless, `SELECT … FOR UPDATE` locking
mechanism (docs/08). **Not frozen:** the exact scheme.

| # | Question | Why it matters | Answer | Confirmed by | Date |
|---|---|---|---|---|---|
| N1 | Must invoice numbering be continuous for the life of the company's VAT registration (no annual reset), or is annual reset acceptable? | The existing numbering mechanism (reused from order numbers) resets per calendar year by construction. If continuous numbering is legally required, this is a schema change, not a config toggle — must be known before the numbering code is written. | | | |
| N2 | What is the exact required number format (digit count, leading zeros, any prefix)? | `invoices.number` is currently a plain `bigint`; the display format (e.g. 10-digit zero-padded) is unspecified anywhere in the frozen docs. | | | |
| N3 | Does the number reset (or not) if the company's VAT-registration status changes mid-year? | Edge case not covered by N1 alone; affects the sequence's key design. | | | |

## 2. Legal invoice template

Frozen today: exactly two PDF documents ship in V1 (protocol + Фактура,
docs/02 §13); currency EUR (docs/00 Q3); language Bulgarian only (ADR-015).
**Not frozen:** the template content.

| # | Question | Why it matters | Answer | Confirmed by | Date |
|---|---|---|---|---|---|
| T1 | What is the complete required field set for the supplier (seller) section? | `companies.requisites` is a schemaless JSONB blob today — nothing constrains or validates its keys. | | | |
| T2 | What is the complete required field set for the customer (buyer) section, for both B2C and B2B? | `customers.company_requisites` has the same gap. | | | |
| T3 | What is the exact mandatory Bulgarian legal text (both VAT-registered and non-registered wording)? | docs/02 §11: "exact texts and fields from the accountant review" — nothing has been drafted anywhere in the repo. | | | |
| T4 | Does the document need a payment method/reference line, or does that stay purely operational (kept only in `payments`, never printed)? | No frozen doc asserts either answer; a product display choice pending confirmation. | | | |
| T5 | Are signatures required on the invoice document (unlike — or like — the intake/delivery protocol, which does have signature lines)? | Not addressed by any doc for the invoice specifically. | | | |
| T6 | Is a footer required, and if so what must it contain? | Not addressed by any doc. | | | |
| T7 | Final sign-off: is the assembled template approved for use? | docs/02 §13: "Фактура — per accountant-approved template" — this is the actual release gate, not just field content. | | | |

## 3. VAT rules

Frozen today: two VAT modes exist at the schema level
(`invoices.vat_mode CHECK (registered|not_registered)`, docs/08); the mode
comes from `companies.vat_registered`. **Not frozen:** the computation
rules.

| # | Question | Why it matters | Answer | Confirmed by | Date |
|---|---|---|---|---|---|
| V1 | Per-line VAT rounding, or round once on the invoice total? | Produces different totals on multi-line invoices — a real accounting choice, not an implementation detail. | | | |
| V2 | Tax calculation order (net → VAT → gross, or another order)? | Not addressed by any doc. | | | |
| V3 | Are any exemptions needed (services/products with no VAT line)? | `invoice_lines.vat_rate` is nullable today — the *meaning* of a null rate isn't specified. | | | |
| V4 | Exact wording for non-VAT-registered companies' invoices? | docs/02 §11: "non-registered → „нерегистрирано по ЗДДС" note" — the exact required phrasing is still open. | | | |
| V5 | Is reverse charge in scope for V1? | Never mentioned in any product document — confirm out of scope rather than assume. | | | |
| V6 | Are advance/prepayment invoices (авансова фактура) in scope for V1? | Never mentioned in any product document. Bulgarian VAT law treats these as a distinct instrument with different VAT timing — confirm out of scope rather than assume, since the current schema/lifecycle (Draft → Issue → Annul/Reissue) was not designed with this in mind. | | | |

## 4. Company requisites (feeds a product gate, not just the template)

docs/01 (Company entity): "invoices cannot be issued until legal requisites
are complete" — this is a frozen invariant with **no implementation** yet,
because the required field list doesn't exist.

| # | Question | Why it matters | Answer | Confirmed by | Date |
|---|---|---|---|---|---|
| R1 | What is the exact list of `companies.requisites` keys required before Issue may proceed (ЕИК, ДДС №, МОЛ, address, IBAN — confirm the complete list and which are conditional on `vat_registered`)? | This list is what the Issue-time completeness check validates against (T1 covers the *document's* field set; this covers the *gate's* required-field list — they should end up the same list, but are asked separately since one blocks rendering and the other blocks the action). | | | |

---

## After this document is complete

1. Every row above has an Answer, a confirming accountant name, and a date.
2. The numbering decision (§1) feeds `ADR-BOS-005` if it changes the
   assumed year-scoped mechanism, and the frozen schema docs (01/08/09) if
   the number format needs a dedicated column instead of `bigint`.
3. The template (§2) and VAT (§3) answers become the input to the PDF
   rendering and totals-freeze code in the Invoice Issue slice.
4. The requisites list (§4) becomes both the Issue-time completeness check
   and the field list a future Settings screen must collect.
5. This document is cited from the Invoice Issue implementation slice as
   its accountant sign-off record (docs/12 §4 release gate).
