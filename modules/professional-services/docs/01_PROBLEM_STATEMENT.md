# PS-01 — Problem Statement

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

## 1. The operating reality of the target firm

A typical target firm (see [05_PERSONAS_AND_STAKEHOLDERS.md](05_PERSONAS_AND_STAKEHOLDERS.md)):

- 1–15 people; often 2–5; the owner both sells and produces;
- 10–150 concurrent assignments in flight, mixed service types;
- intake by phone, email, Viber/WhatsApp, personal meeting, referral, or an
  official act (court appointment letter, bank order);
- deliverables with hard external deadlines: court submission dates, bank
  SLAs, statutory terms for acts and passports, contractual delivery dates;
- inputs (documents) that must be extracted from clients, courts, banks,
  municipalities — the single most common cause of stalling;
- no dedicated administrator; record-keeping competes with billable work.

## 2. The failure catalogue (what actually goes wrong)

Each failure below is a design driver; the traceability matrix
([38_TRACEABILITY_MATRIX.md](38_TRACEABILITY_MATRIX.md)) maps them to
requirements.

| # | Failure | Root cause | Consequence |
|---|---|---|---|
| P1 | Missed official deadline | deadline lives in one person's calendar or memory | legal/financial liability, lost client, fines (court expertise) |
| P2 | Forgotten assignment | accepted verbally, never written anywhere authoritative | client discovers weeks later; reputational damage |
| P3 | Unclear ownership | "we all sort of handle it" | nobody chases; duplicated or missing work |
| P4 | Invisible progress | status exists only in the head of the worker | owner cannot answer client; client calls repeatedly |
| P5 | Stalled waiting states | "waiting for documents" with no follow-up owner/date | weeks lost; deadline pressure explodes at the end |
| P6 | Missing documents discovered late | no checklist of required inputs at intake | inspection/valuation must be redone or delayed |
| P7 | Inactive case unnoticed | no signal distinguishes "quiet because fine" from "quiet because forgotten" | P1/P2 by another route |
| P8 | Poor prioritisation | no comparable view of urgency across assignments | urgent work displaced by loud work |
| P9 | Uneven workload | no per-person view of active load and due dates | one person drowns while another idles; deadlines slip |
| P10 | Lost communication history | agreements made by phone, recorded nowhere | disputes; repeated questions; no handover possible |
| P11 | Delivery/payment blindness | delivered but not invoiced; invoiced but unpaid, unnoticed | cash-flow loss for firms with the thinnest margins |
| P12 | Un-reconstructable history | changes (esp. deadline moves) leave no trace | no accountability; no defence in disputes |

## 3. Why existing tools do not solve it

- **Excel** solves the register (partially P2) but nothing time-based: no
  warnings, no next actions, no history, no files, single-user editing.
- **Generic task managers** model tasks, not engagements: no client, no
  official-vs-internal deadline distinction, no dossier, no delivery/payment,
  English-first, and they happily let an "In Progress" card sit forever (P7).
- **Practice-management / PSA suites** exist for law and accounting but are
  enterprise-priced, English-first, and demand more administration than a
  3-person firm can spend (violates the pragmatism directive if we imitate
  them).
- **Calendar + email** capture appointments and threads but cannot answer
  "what is the state of assignment X" or "what has no next action".

## 4. The problem, in one sentence

Small professional-service firms lack a single, low-friction operational
register that binds every accepted assignment to an owner, a stage, a next
action, and its deadlines — and that actively surfaces the assignments that
are about to fail (P1, P5, P7) instead of waiting to be asked.

## 5. Constraints on any solution

- **Effort budget:** recording reality must cost seconds, not minutes; a
  three-person firm abandons anything heavier (see quick-entry design in
  [18_COMMUNICATION_LOG.md](18_COMMUNICATION_LOG.md), [23_SCREEN_SPECIFICATIONS.md](23_SCREEN_SPECIFICATIONS.md)).
- **Bulgarian-first**, mixed digital literacy, ordinary office hardware.
- **Trustworthy time rules:** deadline and warning behaviour must be exactly
  predictable (Europe/Sofia, documented weekend/holiday semantics) or the firm
  will keep the paper calendar "just in case" — and then the product has lost.
- **Multi-tenant SaaS** on the Business OS platform (docs/14 web-first pivot);
  strict per-organisation isolation (ADR-016).
- **Auditability:** deadline changes, completions, deletions must be
  historised (P12) without turning the product into a compliance tool.
