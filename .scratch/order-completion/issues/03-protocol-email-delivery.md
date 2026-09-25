# Email the completion protocol (with optional warranty section)

Status: done (2026-09-25)

## Context

No code today sends the protocol PDF by email — only print exists
(`service_orders/protocol.py` generates the PDF; `OrderHeader.tsx` triggers
a print action). Real SMTP delivery already exists for password reset:
`backend/src/business_os/identity/mail.py` uses `smtplib` with
STARTTLS/auth, and silently no-ops with a `logger.warning` if
`smtp_host`/`smtp_from` are unset — reuse this, don't build a second mail
path.

PO wants two email actions from the post-completion menu:
"Изпрати протокол по email" and "Изпрати протокол + гаранция по email".

**Scope correction (2026-09-25, after issue 02 landed):** issue 02
deliberately did NOT build the three-action post-completion menu (print /
email / email+warranty) — two of the three actions need this issue's
backend endpoint, and shipping a menu with dead buttons ahead of it would
violate this repo's "no half-finished implementations" rule. So **this
issue now owns the whole menu**, not just the email endpoint: replace the
existing lone "Протокол за предаване" print button (on a `terminal_success`
order, `OrderHeader.tsx`) with the three-action menu/section, print
included — reuse today's `?type=delivery` print logic as-is for the print
action, don't rebuild it.

## Scope

- New backend endpoint (likely `POST /orders/{order_id}/protocol/email`)
  that: generates the protocol PDF (reuse `protocol.py`), attaches it,
  sends via `business_os.identity.mail`'s existing SMTP helper to the
  customer's email on file (`Customer.email`) — decide what happens if the
  customer has no email on record (block with a clear error, per
  `errors.*` message-key convention — don't silently no-op).
- A `include_warranty: bool` param/variant: when true, the emailed PDF (or a
  second attachment) includes the warranty section — company-level terms
  (issue 04) + per-part warranty (issue 05). Reuse whatever section
  `protocol.py` already renders for print, don't duplicate the PDF layout
  logic.
- No PII in logs (root `CLAUDE.md` rule 7) — don't log customer email
  addresses or PDF content on send/failure, only order id + outcome.
- Frontend: build the three-action menu/section (print, email, email+
  warranty) replacing today's single print button, wiring the two new
  actions to this endpoint with a loading/success/error state (follow the
  existing dialog action pattern from `OrderHeader.tsx`'s operation-token
  guard).

## Open question for implementer

Is a delivery failure (SMTP error) surfaced to the user synchronously
(endpoint returns 4xx/5xx) or queued/retried? Given `mail.py`'s existing
password-reset path sends synchronously and surfaces failure, match that —
don't introduce a job queue for this.

## Acceptance criteria

- Backend test coverage: successful send (mock/capture SMTP call, don't hit
  a real mail server in tests — check how `test_password_reset.py` handles
  this and follow the same pattern), missing-customer-email error case,
  warranty-included variant.
- `ruff`/`mypy`/`lint-imports` clean.

## Implementation notes

**Open question resolved**: synchronous, surfaced to the caller — unlike
password-reset's silent-failure posture (anti-enumeration), there's no
equivalent concern for an authenticated shop employee explicitly asking to
send this, so `send_completion_protocol_email` raises `OrderError` (502)
on SMTP failure rather than swallowing it.

**`include_warranty` semantics, decided without issues 04/05** (neither is
built yet — no free-text company terms, no part-warranty-in-months): rather
than block on those, `include_warranty` controls whether
`generate_delivery_protocol` renders the labor/part warranty-day lines it
already unconditionally rendered before this issue (new `include_warranty:
bool = True` param, default preserves the print button's exact prior
output byte-for-byte). `False` (the plain "Изпрати протокол" action) omits
those lines entirely; `True` (the "+ гаранция" action, and the unchanged
print button) keeps them. When issue 04 lands, its free-text terms should
extend this same flag, not introduce a second toggle.

**New public surface**: `business_os.identity.mail.send_email_with_attachment`
(mirrors `send_email`, adds one binary attachment via `EmailMessage.
add_attachment`), exposed to `service_orders` through `identity.contracts`
per the existing `identity-public-boundary` pattern (`get_warranty_defaults`
etc.) — `service_orders` never imports `identity.mail` directly.
`service_orders.service.send_completion_protocol_email` is the new
service-layer function (validates snapshot exists, validates
`Customer.email` is set, builds the PDF, sends, raises `OrderError` on any
failure); `POST /orders/{order_id}/protocol/email` (`{"include_warranty":
bool}`) is the thin router wrapper.

**Frontend**: three buttons (print unchanged, two new email actions) instead
of a dropdown — simpler, matches this file's existing plain-button pattern
for the intake/print actions, and three items doesn't yet justify the
`StatusTransitionMenu` dropdown machinery. Local `emailingAction` state
(separate from the dialog `pending` state machine) disables both email
buttons while either send is in flight and swaps the clicked one's label to
"Зареждане…".

Verified: backend 761 passed (+8: 3 mail-adapter unit tests, 5 endpoint
integration tests) + 1 xfailed, frontend 518 passed (+6), `ruff`/`mypy`/
`lint-imports`/`tsc --noEmit` all clean. Not verified: real SMTP delivery
(all tests monkeypatch `mail.send_email_with_attachment` — appropriate for
unit/integration tests, but this repo has no environment with real SMTP
credentials configured, so actual outbound delivery has never been
observed end to end for either this or the pre-existing password-reset
path).
