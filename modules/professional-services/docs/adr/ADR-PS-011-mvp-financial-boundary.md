# ADR-PS-011 — MVP financial boundary (money-light)

Status: **Proposed** · Date: 18.07.2026

## Context

Firms need payment/delivery visibility (pain P11), but the platform's
invoicing future is already assigned: the commercial module (Етап 4, BOS-02
group B, designated first shared-module candidate). Building invoice
mechanics here would duplicate it; waiting for it would delay the MVP;
skipping money entirely would ignore a commissioned pain.

## Decision

- **Inside the module, minimal:** `agreed_price` + currency +
  `payment_due_on` on the assignment; `ps_payment_entries` facts (advance /
  payment / expense / invoiced_record). Totals (invoiced, paid,
  outstanding) always derived, never stored (INV-8).
- **Never in the module:** invoice issuance, numbering, VAT, PDFs,
  ledgers, dunning.
- **Future:** commercial-module integration via its contract; PS's
  `invoiced_record` entries then carry a structured `external_ref` to real
  invoices. No backfill required; manual history stays valid.
- Financial visibility/edit rights per the role matrix; server-side
  response shaping, worker visibility off by default (Q-6).
- Financial features may never gate or delay the workflow-and-deadline
  MVP (explicit commissioned constraint, adopted as a rule).

## Consequences

- P11 is answered with three glances (agreed/paid/outstanding) at near-zero
  model cost.
- The firm's accountant still does accounting elsewhere — by design.
- When Етап 4 lands, integration is additive; the only debt is one entry
  kind gaining a structured reference.
