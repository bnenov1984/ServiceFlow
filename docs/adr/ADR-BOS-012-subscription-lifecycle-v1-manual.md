# ADR-BOS-012 — Subscription/Licence Lifecycle (V1, Manually Managed)

Status: **Proposed (audit-driven, 26.07.2026) — awaiting PO review; not part of
the frozen ADR set. Narrows ADR-018 for an earlier, payment-provider-free
landing; does not replace it.** · Source: docs/business-os/18 (audit),
ADR-018 (target design), ADR-009 (degradation philosophy, carried forward)

## Context

ADR-018 already designed the target subscription model: 14-day trial, one
monthly EUR plan, a `PaymentProvider` port, a signature-verified webhook
inbox, dunning, read-only degradation on expiry — all **Documented, not
built** (docs/business-os/17). This task explicitly forbids adding real
payment/billing integration now ("no automated card billing, no Stripe or
other payment provider") while explicitly permitting a V1 that chooses
manually managed subscriptions. Without *some* lifecycle, the Vendor Console
(ADR-BOS-009) has nothing concrete to manage. This ADR supplies exactly that
— states and who transitions them — without touching payment mechanics.

## Decision

- **Scope: V1 only, explicitly narrower than ADR-018, not a replacement.**
  Same state vocabulary as ADR-018 so nothing renames when automated billing
  lands later.
- **States**: `trial → active → grace_period → suspended → cancelled`.
  - `trial` — full-featured, vendor-created (no self-service signup in this
    ADR's scope — company/first-Owner creation is a Vendor Control Plane
    action per ADR-BOS-009; self-service registration is ADR-018's own
    future scope, unchanged by this ADR).
  - `active` — normal paid standing (V1: "paid" is recorded by the vendor
    administrator from whatever payment happens outside the app — bank
    transfer, invoice, anything; the app does not care how, only that a
    vendor administrator asserts it).
  - `grace_period` — carried from ADR-009's philosophy: full functionality,
    a visible countdown/explanation, entered manually by a vendor
    administrator (not by a failed webhook, since none exists yet).
  - `suspended` — read-only degradation (below); entered manually, always
    with a reason.
  - `cancelled` — terminal; also the landing state for a `trial` that was
    never converted (an "expired trial" is `cancelled` with a reason noting
    why, not a fifth state).
  - **`past_due` (ADR-018) is deliberately omitted in V1** — it exists only
    to describe the automated window between a failed card charge and
    suspension; with no payment provider, a vendor administrator moves a
    company directly to `grace_period` or `suspended` by hand.
- **Transitions are Vendor-Administrator-only, always with a mandatory
  reason**, recorded append-only (actor, company, old state, new state,
  reason, timestamp) — the same reasoned-change shape `PSDeadlineChange`
  and `PSAssignmentStageHistory` already established, reused rather than
  invented (`platform_audit_log`, ADR-BOS-009 §Decision, covers this).
  Tenant Owners never see or trigger a transition, only the resulting state
  and its plain-language explanation.
- **Degradation is unchanged from ADR-009/018**: `grace_period` and
  `suspended` both mean full data visibility, export/backup always
  available, mutations blocked with an explanation and a renewal path. This
  ADR does not redefine degradation — only how a company enters it in V1 (a
  vendor action, not a webhook).
- **Enforcement point**: a single request-scoped dependency,
  `require_subscription_ok` (Core-owned, sibling to ADR-BOS-010's
  `require_<module>_active`), checked on mutating tenant requests only —
  reads and export/backup endpoints never gate on it, mirroring ADR-009's
  "export always" guarantee mechanically, not just by policy. **Not built by
  this ADR** (Phase 4 constraint) — this ADR fixes its name and where it
  sits in the dependency chain so ADR-BOS-010's future work composes with it
  cleanly.
- **Entitlement and subscription state stay independent** (ADR-BOS-010 §3,
  restated here from the other side): suspending a company's subscription
  does not change its `active_modules`; a vendor administrator can revoke
  one module's entitlement without touching subscription state at all.
- **Trial length, plan count, and pricing are not re-decided here** — they
  are ADR-018's numbers (14 days, one plan, EUR), inherited unchanged.

## Alternatives considered

- **Build ADR-018's full webhook/provider machinery now** — rejected by
  explicit task constraint and by the distraction risk already named in
  docs/business-os/09 (R-1); also unnecessary, since the state machine below
  is byte-for-byte forward-compatible with ADR-018 once a provider exists.
- **No lifecycle at all — vendor just flips the entitlement boolean off to
  "suspend"** — rejected: conflates commercial standing with entitlement,
  which this task's own security requirements explicitly separate
  ("entitlement state must not be confused with feature configuration," and
  by the same logic, not with billing state either — ADR-BOS-010 §3/§4).
- **Skip `grace_period`, go straight `active → suspended`** — rejected;
  contradicts the already-accepted "data is never hostage, always give a
  buffer" product value (ADR-009, carried into ADR-018); a manual grace
  period costs nothing extra to keep.
- **Model states as a free-text field instead of an enum** — rejected;
  degradation behavior branches on state, an enum is the whole point of a
  state *machine*, and ADR-018 already committed to named states.

## Consequences

- The Vendor Console's subscription screen (docs/business-os/18 §V1 scope,
  item 7) has a small, concrete state machine to build against immediately,
  independent of payment-provider selection/verification — which ADR-018
  itself flags as a real external risk ("provider availability/terms for BG
  — verified before Stage coding").
- When automated billing lands, only the *transition trigger* changes
  (webhook replaces a vendor click for `active`⇄`past_due`⇄`suspended`); no
  state is renamed, no degradation behavior changes, no tenant-facing
  contract changes.
- A new migration is required (subscription-state column(s) on `companies`
  or a small sibling table, plus the audit table already proposed in
  ADR-BOS-009) — **not authored by this ADR**; see docs/business-os/18 §6.

## Reconsideration triggers

ADR-018's payment-provider integration actually starts — at that point this
ADR is superseded/merged into ADR-018, the same relationship ADR-009 has to
ADR-018 today.
