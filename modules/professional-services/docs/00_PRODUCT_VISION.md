# PS-00 — Product Vision

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

## 1. The problem

A small Bulgarian professional-service firm — a construction supervision
company, a valuation firm, a court-appointed expert, an engineering or
accounting office — runs on assignments received by phone, email, Viber, or in
person. Each assignment carries an official deadline (a court date, a bank's
valuation deadline, an act-signing date), a set of documents that must be
collected, and a deliverable that must go out.

The firm's operational memory is fragmented: notebooks, Excel files, Word
documents, mail threads, personal calendars, local folders, and the owner's
head. The observable failures are always the same:

- a deadline is noticed too late or missed outright;
- an accepted assignment is simply forgotten until the client calls;
- nobody can say who owns a case or what its actual state is;
- clients call repeatedly to ask for updates because the firm cannot push them;
- work stalls silently — "waiting for documents" with no one chasing them;
- delivery and payment status are invisible until someone reconstructs them.

These are not software-sophistication problems. They are **operational
visibility** problems in firms of 1–15 people with limited time and mixed
digital literacy.

## 2. The vision

**Every assignment answers seven questions at a glance:** what is it, who is
responsible, what stage is it in, what happens next, when is that due, when is
the final deadline, and what is missing. If any answer is absent, the system
says so loudly.

Three product pillars:

1. **Next Action** (следваща стъпка). "In Progress" is not operational
   knowledge. Every active assignment normally carries one concrete next
   action — description, owner, due date. Assignments *without* one are
   surfaced as a first-class risk, because that is exactly how work gets
   forgotten. See [14_NEXT_ACTION_MODEL.md](14_NEXT_ACTION_MODEL.md).
2. **Deterministic deadline & inactivity engine.** Risk states (attention /
   urgent / critical / breached; stale / blocked / never-started) are computed
   from stored data by pure, testable rules in Europe/Sofia time — always
   reproducible, never colour-only, never AI-decided. See
   [13_DEADLINE_AND_REMINDER_ENGINE.md](13_DEADLINE_AND_REMINDER_ENGINE.md).
3. **One dossier per assignment.** Documents, communication history, tasks,
   deadline changes, and money — attached to the assignment, append-only where
   it matters, so the firm can always reconstruct what happened and prove it.

The product is deliberately a **control tower, not a production tool**: it
does not draft the expert report or compute the valuation. It makes sure the
report is drafted on time, by the right person, with all inputs present, and
that the client hears about it.

## 3. Who it is for

Primary: Bulgarian professional-service firms of 1–15 people whose work is
assignment-shaped: construction supervision (independent of, and complementary
to, the Construction Documentation module), real-estate valuation, court
expertise, engineering/technical consulting, architecture, surveying, legal
and administrative services, accounting, document preparation.

The buyer is the owner/manager; daily users are the professionals themselves
plus occasionally an office assistant. This matches the Business OS pragmatism
directive size class (2–10, here stretched to 15) — no enterprise features.

## 4. Differentiators vs. what firms use today

| Against | Why we win |
|---|---|
| Notebook + memory | nothing is forgotten; deadlines computed, not remembered |
| Excel register | ownership, next actions, warnings, history, files — not just rows |
| Generic task apps (Trello/Todoist) | assignments ≠ tasks: deadlines with legal weight, client linkage, dossier, delivery & money, Bulgarian-first |
| Enterprise PM/PSA tools | installable attention span: usable without training, priced and sized for a 3-person firm |

## 5. Relationship to the Business OS product family

The module is a **vertical module** in the Business OS modular monolith,
parallel to ServiceFlow (repair shops) and Construction Documentation
(structured document generation). It reuses Core — tenancy, identity, storage
port, event bus, i18n mechanism — through public contracts only, and owns its
entire vertical domain. Where Construction Documentation *produces* specialised
outputs (acts, technical passports), this module *manages the engagement*
around them; the two link, they do not merge
([29_CONSTRUCTION_DOCUMENTATION_INTEGRATION.md](29_CONSTRUCTION_DOCUMENTATION_INTEGRATION.md)).

## 6. What success looks like

- A three-person valuation firm runs its whole register here within one week
  of self-onboarding, without training.
- Zero missed official deadlines for firms that keep the register current —
  and every near-miss visibly escalated days in advance.
- The morning ritual: open the dashboard, see overdue / due-today / due-soon /
  stale / no-next-action, and know exactly what to do first.
- The module ships on Core without modifying a single ServiceFlow domain file
  — the Business OS platform proof (BOS-00 §9).

## 7. Non-vision (see 02_SCOPE_AND_GUARDRAILS.md)

Not a document-generation engine, not an accounting system, not a client
portal, not a generic project-management platform, not an AI product. AI may
later summarise and suggest at the edges; it never owns a deadline or a
status.
