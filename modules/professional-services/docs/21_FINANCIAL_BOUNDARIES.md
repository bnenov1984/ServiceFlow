# PS-21 — Financial Boundaries

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Commissioned question: does the financial model live in the module, in a
shared billing capability, behind contracts, or later? **Answer: a minimal
model inside the module now; real invoicing behind the future commercial
module's contract; nothing financial may delay the workflow-and-deadline
MVP** (ADR-PS-011).

## 1. What the firm actually needs operationally (P11)

Not bookkeeping — three glances: *what did we agree, what has been paid,
who owes us*. That is visibility, achievable with two small structures:

- On `Assignment`: `agreed_price numeric(12,2)?`, `currency` (default BGN),
  `payment_due_on date?`.
- `PaymentEntry` (`ps_payment_entries`): assignment_id, kind ∈ `advance |
  payment | expense | invoiced_record`, amount, on_date, note, created_by.
  `invoiced_record` notes that/when an invoice was issued externally
  (number in the note) — the module does **not** issue invoices.

Derived, never stored (NFR-PS-07, INV-8): invoiced = Σ invoiced_record;
paid = Σ advance+payment; outstanding = agreed − paid (shown only when
agreed_price present); expenses listed separately (informational; no
margin analytics — [02] §2.5).

## 2. Signals

- `payment_overdue`: agreed_price set ∧ outstanding > 0 ∧ payment_due_on <
  today → notification to managers ([19]); dashboard money chip (S-1) and
  J-8 monthly glance. No dunning, no reminders-to-clients (out of scope).

## 3. Boundary with the commercial module (Етап 4)

When Commercial Documents ships, integration is **contract-consumption,
not migration**: PS offers "издай фактура" → calls the commercial contract
with (client snapshot, amount, assignment reference); the returned invoice
reference is stored as an `invoiced_record` entry with a structured ref.
PS keeps rendering its derived totals; the commercial module owns the
invoice truth (numbering, immutability, BR-1/BR-2 discipline). Existing
manual entries stay valid history — no backfill required (FR-PS-103).
This module must not build gapless numbering, VAT, or invoice PDFs — that
would duplicate the platform's designated shared-module candidate (BOS-02
group B) and is a review-blocker.

## 4. Boundary with platform subscription billing

ADR-018 subscription billing (what tenants pay the platform) is entirely
unrelated to this document and never touches `ps_*` tables.

## 5. Permissions & privacy

Money visibility/edit per the role matrix ([20] §3): owner/manager always;
worker via org toggle (default off); readonly per-user toggle (accountant).
Money fields are excluded from list endpoints for users without visibility
(server-side shaping, not CSS hiding). Amounts never appear in
notifications' message params beyond presence ("просрочено плащане"), so a
role change never leaks history through old notifications.
