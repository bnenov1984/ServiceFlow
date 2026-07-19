# ADR-PS-002 — Relationship to ServiceFlow and Business OS

Status: **Proposed** · Date: 18.07.2026

## Context

The commission requires a module that is parallel to ServiceFlow, reuses
suitable capabilities, and is not a renamed clone. The platform already has
binding rules: BOS-04 dependency rules, BOS-05 data ownership, BOS-06
module contract, BOS-08 Phase-5 "build own or wait", BOS-16 Identity
public boundary. The full capability audit is PS-27.

## Decision

1. Professional Services is a **Business OS vertical module #3**, consuming
   Core exclusively through published contracts (`identity.deps`,
   `identity.contracts`, `shared_kernel` primitives, i18n mechanism,
   platform services as they land).
2. **Zero relationship to ServiceFlow's domain**: no imports, no table
   access, no consumed events, no shared entities — Separate Ways (PS-10
   §2). Enforced by import-linter + mapper-ownership tests from the first
   code PR.
3. Where ServiceFlow has a capability this module wants (tasks, files
   pipeline, contacts, timeline, numbering), this module **builds its own**
   minimal version, deliberately shaped for later Phase-6 comparison —
   never extended-in-place, never extracted pre-emptively.
4. Five ServiceFlow **patterns** are adopted as disciplines (not code):
   single transition chokepoint; append-only history via DB trigger;
   normalization-backed duplicate detection; guided anonymization; typed
   JSONB details. Recorded in PS-27 §3.
5. AI is never load-bearing: no core workflow requires it, and no AI
   feature may ever write deadlines, states, or next actions (suggestions
   only, labelled).

## Consequences

- Deliberate near-term duplication (tasks, files, notifications-adjacent
  code) — the platform-sanctioned price for honest extraction evidence.
- This module's commitment activates BOS-08 Phase 3 (Core rename) and
  minimal activation — platform PRs coordinated in PS-35 Stage 0, not
  bundled into module work.
- The module is the platform's second concurrent proof (with CS): if it
  ships without touching ServiceFlow domain files, Business OS works.
