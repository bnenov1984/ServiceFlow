# PS-38 — Traceability Matrix

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Four chains: pain → requirement → design → screen → test/acceptance.
Granularity is deliberately at the cluster level — a row per FR would be
maintenance theatre; clusters keep the matrix true and cheap to keep true.
The consistency review (§3) records the checks performed on this package.

## 1. Pain-to-proof chains

| Pain ([01] §2) | Requirements | Design | Screens | Tests / acceptance |
|---|---|---|---|---|
| P1 missed official deadline | FR-PS-021, 040–043 | [13] §1–5 | S-1, S-2(+b), S-4 risk strip | T-2/T-3; AC-6/7/8 |
| P2 forgotten assignment | FR-PS-020, 084; J-1 | [09], [11] | S-3, S-1 | T-10 J-1; AC-1 |
| P3 unclear ownership | FR-PS-020 (owner), 022; INV-3 | [09]; [11] | S-2 owner col, S-9 | T-1; T-12.5; AC-12 |
| P4 invisible progress | FR-PS-024, 071, 084 | [12], [18] | S-4, S-1 | AC-2; T-10 |
| P5 stalled waiting | FR-PS-044 (I-5), 030 | [14] §4; [13] §6 | S-1 buckets, S-4 | T-4; AC-9 |
| P6 missing documents late | FR-PS-012, 060 | [17] §1 | S-4 Документи, S-1 | T-10 J-4; AC-4 |
| P7 inactive unnoticed | FR-PS-032, 044 | [13] §6, [14] N-2 | S-1, S-10 | T-4/T-5; AC-9/10 |
| P8 poor prioritisation | FR-PS-040, 080, 084 | [13] §3; [22] §3 | S-1, S-2 | AC-2 |
| P9 uneven workload | FR-PS-085 | [22] §3 | S-9-view | AC-2 (workload chips); T-11 |
| P10 lost communication | FR-PS-070–071 | [18] | S-4 feed | T-10; AC-15 |
| P11 payment blindness | FR-PS-100–102 | [21] | S-4 Финанси, S-1 chip, J-8 | T-6 shaping; AC-12 |
| P12 unreconstructable history | FR-PS-034, 042, 113; INV-10/11 | [30] §2 | S-4 История | T-7; AC-13 |

## 2. Requirement-priority ↔ MVP consistency

[07]'s M/P/F letters and [34]'s lists were cross-checked line by line; one
divergence found and fixed during review (FR-PS-041 override → P in both).
Rule going forward: a priority change edits **both** documents in one PR.

## 3. Consistency review record (Phase-5 of the commission — performed 18.07.2026)

Checks run over the whole package; findings fixed in place before delivery:

1. **Terminology sweep** against [04]: no unqualified "deadline"/"status"
   as entity terms in normative text; ServiceFlow vocabulary absent from
   module UI/schema surfaces. Fixed during authoring: early draft of [02]
   §2.3 pointed at a non-existent workload doc — corrected to [07]+[23].
2. **Status-name consistency:** lifecycle enum (`active/delivered/
   completed/cancelled`) identical in [04]/[11]/[25]/[26]; stage
   categories (5 values) identical in [04]/[12]/[25]; risk vocabulary
   (10 labels) identical in [04]/[13]/[19]. `undelivered_closeout` chosen
   over an earlier `undelivered` draft label — [04] updated.
3. **Data-model reconciliation:** every entity in [09] has exactly one
   table in [25] (fix applied: `ps_assignment_links` was missing; table
   count corrected); every [26] invariant names its enforcement mechanism
   that exists in [25] (partial uniques, triggers, constraints).
4. **Shared-module assumptions verified against the repo:** Core
   contracts (BOS-16), storage port, event bus, normalization exist as
   claimed in [27]; notifications/clients/tasks confirmed **absent** from
   the platform, so "build own" claims are true; commercial module
   confirmed empty (verdicts R-FUT sound). CS module confirmed docs-only
   (A-7) — [29] gated accordingly.
5. **Ownership clarity:** all 22 `ps_*` tables owned by this module;
   no FK leaves the module except `user_id` to Core (documented [25] §5);
   `document_sequences` untouched ([27] §2.4).
6. **Traceability gaps:** every pain has a chain (§1); every AC maps to
   ≥1 FR; F-class refusals each carry a trigger ([34] §3) — none dangle.
7. **Overengineering pass:** items cut during this review rather than
   shipped as design: separate WorkflowInstance entity, `ps_deadlines`
   polymorphic table, per-template transition matrices, org-defined stage
   categories, structured addresses, standalone todos, WIP-limited
   Kanban. Each cut is recorded at its site with the reason.

## 4. Standing rule

This matrix is updated in the same PR as any change to [01], [07], [34],
[37], or the model docs — a stale matrix is treated as a failing check in
doc review, the same way the platform treats stale BOS docs.
