# Order completion: "Приключена" status + warranty terms

## Source

Wave 4 audit (2026-09-25 session) of PO items **7** and **38**. Original Wave 4
implementation (commits `8e9c368`, `d148ea9`) diverged from the PO's ask: it
reused the existing `delivered`/"Предадена" terminal status instead of adding
a distinct post-Ready completion step, and warranty settings only captured
day-counts, not free-text conditions. PO reviewed the divergence and gave a
corrected spec (see decisions below) rather than accepting the as-built
version.

## PO decisions (2026-09-25)

- "Приключена" **replaces** "Предадена" as the terminal-success status —
  not an additional status after it. One `terminal_success` status, renamed.
- A primary button "Приключи поръчката" on a `ready` order drives this
  transition (replaces today's delivery-trigger button).
- After completing, the user gets three actions: print protocol, email
  protocol, email protocol + warranty.
- Company (firm-level) warranty terms become a real settings section:
  standard warranty term, warranty conditions, warranty text, additional
  conditions — free text, not just day-counts. Set by Vendor/Admin at
  company onboarding, editable afterward by the company Owner. (Note: this
  revises the PO's earlier-stated principle that Vendor should never set
  commercial terms — flagged to the PO, they confirmed proceeding as
  specified above.)
- Part-level warranty switches from days to **months** as the input/display
  unit.
- The completion/warranty document must be able to pull from both the
  company-level terms and the specific parts' individual warranties.

## Current state (as of `cf6cb13`)

- `backend/src/serviceflow/service_orders/statuses.py`: terminal-success
  status is `delivered` ("Предадена"), kind `TERMINAL_SUCCESS`. No
  `completed`/"Приключена" status exists.
- `frontend/src/order/OrderHeader.tsx` + `frontend/src/order/dialogs/DeliveryDialog.tsx`
  drive the `ready -> delivered` transition; produces `completion_snapshot`
  (migration `0026`) and a protocol PDF via `service_orders/protocol.py`.
  No email delivery of the protocol exists yet.
- Warranty: `ServiceOrder.warranty_days` (order/labor-level) +
  `PartLine.warranty_days` (part-level, migration `0025`) — both in days.
  Company-level defaults: `business_os/identity/service.py`
  `company.settings.repairflow.warranty_defaults = {labor_days, parts_days}`
  — numbers only, no free text. Owner-only edit via
  `frontend/src/settings/CompanyRequisitesPage.tsx`'s `WarrantyDefaultsSection`.
- Real SMTP email delivery already exists for password reset
  (`business_os/identity/mail.py`) and can be reused for protocol email.

## Issues

1. [01-rename-delivered-status-to-completed.md](issues/01-rename-delivered-status-to-completed.md)
2. [02-completion-button-and-protocol-actions.md](issues/02-completion-button-and-protocol-actions.md)
3. [03-protocol-email-delivery.md](issues/03-protocol-email-delivery.md)
4. [04-company-warranty-terms-settings.md](issues/04-company-warranty-terms-settings.md)
5. [05-part-warranty-in-months.md](issues/05-part-warranty-in-months.md)

Suggested order: 01 → 02 → 03, and 04 → 05 (independent of the status-rename
chain, can run in parallel).
