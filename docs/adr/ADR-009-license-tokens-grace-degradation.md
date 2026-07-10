# ADR-009 — Signed License Tokens, 30-Day Grace, Read-Only Degradation

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §D9, Q1 decision, approved OQ-A1

## Context
The commercial model is subscription even for local deployment (PO decision Q1,
39–49 €/month indicative), but daily work must not require internet, and customer
data must never be hostage to billing state.

## Decision
The application holds a vendor-signed, offline-verifiable license token (company,
plan, expiry). A background job (ADR-006) refreshes it whenever internet exists,
piggybacking version/health telemetry for the vendor console (A4 scope). Full
functionality continues through a **30-day offline grace** after the last successful
refresh. Expired subscription or exhausted grace ⇒ **read-only mode**: all data
visible, export and backup always functional, mutations blocked with a plain
explanation and renewal path. Vendor console can extend/suspend/override per install.

## Alternatives considered
- **Always-online license checks** — violates the no-internet requirement; one ISP
  outage stops a workshop. Rejected.
- **Perpetual licenses / manual keys** — PO explicitly rejected perpetual; manual
  keys give no subscription enforcement and no support telemetry. Rejected.
- **Hard lockout on expiry** — commercially self-destructive and reputationally
  fatal in a small market; data-hostage behavior contradicts product values. Rejected.

## Consequences
- **Advantages:** recurring revenue with honest offline tolerance; support telemetry
  arrives with license refreshes; degradation preserves trust ("your data is always
  yours").
- **Disadvantages:** a minimal vendor cloud becomes V1 scope (03 §4); token/refresh
  logic must be bulletproof against clock tampering (signed timestamps, monotonic
  checks — sophisticated tampering is accepted as not worth an arms race).
- **Risks:** vendor cloud outage cascading into shop anxiety. Mitigation: 30-day
  buffer absorbs any realistic outage; grace status shown honestly in settings.

## Reconsideration triggers
SaaS edition replaces tokens with live subscription state (same entitlement
interface); grace length is a tunable, not an ADR change.
