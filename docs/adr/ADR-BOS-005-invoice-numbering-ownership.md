# ADR-BOS-005 — Invoice Numbering Ownership (`document_sequences`)

Status: **Accepted** · Date: 20.07.2026 · Source: docs/business-os/09 Q2,
docs/business-os/05 §1, ADR-BOS-003 (flagged this as the one open ownership
item), the Invoice Issue decision-closure analysis (this session)

## Context

`document_sequences` (`company_id, kind, year, current`) is today's only
"open" table ownership question (ADR-BOS-003: "exactly one ownership
question is open — `document_sequences` — orders write it now, invoices will
in Етап 4"). It is filed under `commercial` in prose (docs/08 §commercial)
but owned in code by `service_orders`, whose `next_number()` already uses it
for order numbering via `SELECT … FOR UPDATE` (the frozen single
gaplessness point, docs/08). No code path for invoice numbering exists yet —
the Invoice Draft slice never calls it.

Earlier this session, the commercial ↔ `service_orders` boundary was
mechanically repaired: two import-linter `protected` contracts
(`service-orders-public-boundary`, `commercial-public-boundary`) now block
either module from importing the other's internals. The one existing
"backward" data need (`service_orders` reading commercial-owned
`paid_amount`/`balance`) was solved by a port `service_orders` owns and
`commercial` implements, wired once by the composition root — not a raw
import in either direction. Invoice numbering is a different shape: the data
need runs the *already-sanctioned* way (`commercial` needs something from
`service_orders`), so no new port is required — extending the existing
outbound contract is enough.

Three ownership options were evaluated:

- **A. `commercial` owns it** — `service_orders` would have to call *out* to
  `commercial` for its own order numbers, inverting the direction just
  repaired. A partial move (invoices only) leaves order numbering either
  duplicated or coupled to `commercial` for no functional gain.
- **B. `service_orders` keeps it, exposes a contract** — zero new
  dependency direction; `commercial` already imports `service_orders`'s
  contract module for everything else (`get_order_summary`,
  `get_order_total`, `get_order_lines`).
- **C. New shared/platform numbering service** — cleanest in the abstract,
  but BOS-09 Q2 itself says this "is only proposable when a second real
  module issues numbered documents" — `professional_services` doesn't, so
  there is no second consumer today.

## Decision

**`document_sequences` stays owned by `service_orders`.**
`service_orders/contracts.py` gains one more outbound function (e.g.
`get_next_invoice_number(db, ctx) -> str`) that `commercial` calls exactly
like it already calls `get_order_total`/`get_order_lines` — same module,
same direction, same locking mechanism (`SELECT … FOR UPDATE`), no new
architectural shape. `service_orders` imports nothing from `commercial` to
make this work.

This closes BOS-09 Q2 with its option **(b)** ("service_orders keeps it,
commercial calls an orders contract") and discharges the obligation
ADR-BOS-003 recorded: "Етап 4 must resolve `document_sequences` ownership
before invoices write it."

## Dependency direction

- `commercial` → `service_orders.contracts` — **allowed**, existing edge,
  extended with one more function. This is the only permitted direction.
- `service_orders` → `commercial` — **forbidden**, unchanged. The two
  `protected` import-linter contracts already enforce zero imports either
  way beyond each module's own `contracts.py`.
- No inversion port is introduced for this edge (unlike
  `PaymentSummaryProvider`): the data need already flows in the sanctioned
  direction, so extending the existing one-way contract is sufficient.

## Alternatives considered

- **A (commercial owns it)** — Rejected. Would require `service_orders`,
  the current working owner of order numbering, to call *out* to
  `commercial` for its own numbers — recreating exactly the cycle-shaped
  coupling the boundary repair removed, just moved to a different table.
- **C (new shared numbering service)** — Rejected for now. No second real
  module issues numbered documents yet (BOS-09 Q2's own precondition for
  this option); building it today would be premature generalization against
  the project's pragmatism directive (CLAUDE.md rule 1).

## Consequences

- **Advantages:** zero migration; zero new dependency direction; reuses the
  exact contract pattern already proven twice this session; one locking
  authority avoids the two-writers-one-table risk that made this the "first
  genuinely shared-write table" flagged in BOS-05 §1.
- **Disadvantages:** `service_orders` keeps a responsibility (invoice
  numbering) that doesn't conceptually belong to its domain — an accepted,
  pre-existing mismatch (docs/08 already filed the table under `commercial`
  in prose while the code owned it elsewhere), not a new one introduced by
  this decision.
- **Risks:** the existing `next_number()` locking implementation has a
  latent race on first-use-per-`(company, kind, year)` — a plain `SELECT`
  finding no row, followed by an `INSERT`, is not itself lock-protected, so
  two concurrent transactions can both attempt the insert and one loses to
  an unhandled `IntegrityError` instead of retrying. Found during the
  Invoice Issue decision-closure analysis; unexercised by any existing test
  (docs/12 P0-2 names concurrent issue as a release blocker, but nothing
  tests it today for orders or invoices). **Must be hardened before invoice
  numbering reuses this function** — a failed invoice-issue is a worse
  user-facing event than a failed order-create.
- **Follow-up (not performed by this ADR):** docs/business-os/05 §1 and
  BOS-09 Q2 should be updated to mark this Open item Resolved, and
  docs/07_ADR_INDEX.md should list this ADR, in a same-PR-style doc
  amendment per the docs/07 change process — left for the implementation
  slice that actually adds `get_next_invoice_number`.

## Reconsideration triggers

A second module appears that issues its own numbered documents (revisit
option C, per BOS-09 Q2's own condition for it) — or the year-scoped
sequence proves incompatible with the confirmed Bulgarian VAT numbering
rule (revisit the *schema*, a separate accountant-gated decision tracked in
`docs/ACCOUNTANT_REVIEW.md`, not the ownership decided here).
