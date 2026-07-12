# ADR-018 — Subscription & Billing Model (SaaS)

Status: **Accepted** (carried decisions pending PO re-confirmation, doc 14) ·
Date: 11.07.2026 · Supersedes ADR-009 (offline license tokens) for the primary
edition.

## Context
The pivot makes subscriptions a V1 feature. The PO approved the commercial shape
for this exact product on 10.07.2026 (SaaS discovery round): free trial without
card, one paid plan, automated monthly card billing, full admin oversight.

## Decision
- **Trial:** 14 days, full-featured, no card; mandatory email verification.
- **One plan, monthly, EUR**, provider-abstracted card billing (`PaymentProvider`
  port: create customer, start/cancel subscription, parse webhook). Provider
  recommendation Stripe-class, **verified for Bulgaria at implementation time**.
- **Webhook inbox table**: signature-verified, idempotent, replay-safe, audited
  (same discipline the local license design had).
- **Subscription states:** trialing → active → past_due (7-day dunning) →
  suspended → cancelled/expired; evaluated per authenticated request via one
  entitlement dependency.
- **Degradation is kept from ADR-009's philosophy:** expired/suspended = read-only
  + export always available. Data is never hostage — this survives the pivot
  because it is a product value, not a licensing mechanism.
- **Platform admin console** (vendor): all companies, subscription states, extend
  trial, suspend/reactivate, manual override with reason; all actions audited; no
  browsing of tenant business data beyond counts.

## Alternatives considered
- Manual invoicing first — ships earlier but delays true self-serve; rejected by
  PO in the 10.07 round (automated chosen); manual override remains the escape hatch.
- Multiple plans/annual/coupons at launch — explicitly excluded; entitlement
  mechanism keeps the path open.

## Consequences
Advantages: real recurring revenue from day one; support burden shifted to a
console instead of license debugging. Disadvantages: billing edge cases enter V1
(the webhook inbox + one plan + one interval keep the state machine minimal).
Risks: provider availability/terms for BG — verified before Stage coding; port
isolates the blast radius.

## Reconsideration triggers
Second plan tier; annual billing demand; provider policy changes.
