# PS-05 — Personas and Stakeholders

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Composite personas derived from the three reference service lines
([03_DOMAIN_KNOWLEDGE_BIBLE.md](03_DOMAIN_KNOWLEDGE_BIBLE.md)). They drive
journey design ([06](06_USER_JOURNEYS.md)), permissions ([20](20_ROLES_AND_PERMISSIONS.md)),
and every screen's "user goal" ([23](23_SCREEN_SPECIFICATIONS.md)).

## 1. Primary personas

### P-1 — Мария, owner-professional (valuation firm, 4 people)

- Certified valuer; also the firm's manager, salesperson, and reviewer.
- 60–120 concurrent assignments, mostly bank orders with 3–5-day SLAs.
- Digital comfort: good with Excel and email; suspicious of "systems" that
  cost more time than they save.
- **Needs:** morning risk overview in <1 minute; instant answer when a bank
  calls about any assignment; confidence nothing is silently late.
- **Buys the product if:** the register beats her Excel on day one and the
  deadline warnings prove right on week one.
- Maps to roles: Core owner + module manager.

### P-2 — Георги, employed professional (supervision engineer / junior valuer)

- Executes assignments; on site half the day, often works from a phone in
  the field for lookups, at a desk for real entry.
- **Needs:** "my work today" — his assignments, his next actions, his tasks,
  due dates; quick logging of a call or an inspection in seconds.
- **Fears:** being blamed for a stall that was actually waiting-for-client;
  hence loves blocking reasons and the communication log.
- Maps to role: worker.

### P-3 — Иванка, office assistant (part-time, administrative firm)

- Answers the phone, receives documents, chases clients, keeps the paper
  register today.
- Digital comfort: basic; needs large targets, Bulgarian labels, undo-safe
  forms.
- **Needs:** create an assignment during a phone call in under a minute;
  mark documents received; log communications; see who to chase today.
- Maps to role: worker (she is not a viewer — she writes constantly).

### P-4 — Стоян, court expert (solo practitioner)

- One-person firm; 10–30 concurrent appointments from several courts.
- **Needs:** never miss a submission term or hearing; long quiet waiting
  periods must not generate noise (the hearing *is* the next action).
- Stress-tests: single-user UX — every "assign to" defaults to himself;
  workload view is irrelevant to him; dashboard is everything.

## 2. Secondary personas

- **P-5 Accountant (external or part-time):** needs read-only list of
  delivered/completed assignments with agreed/invoiced/paid amounts for the
  month. Maps to role: readonly (financial visibility on).
- **P-6 Platform operator (Business OS admin):** provisions the tenant,
  activates the module, supports backup/restore. Not a module persona;
  interacts through platform services (Етап 3).

## 3. External stakeholders (never platform users in v1)

| Stakeholder | Touchpoint | Design consequence |
|---|---|---|
| Client (bank, court, investor, individual) | phone/email/paper; asks "докъде сме?" | communication log + statuses make the answer instant; **no client portal in v1** |
| Court / institution | imposes deadlines, hearings, formats | official deadline + appointment modelling; case metadata on court-expertise assignments |
| КНОБ / professional chambers | certification requirements | reviewer step in workflows; no compliance features in module |
| НАП / auditors | may demand records years later | append-only history, no hard deletes of business records ([26](26_BUSINESS_RULES.md)) |

## 4. Anti-personas (explicitly not designed for)

- Firms >~15 people with dedicated PM/admin staff (they need PSA suites).
- Law firms needing court-instance document automation (different product).
- Firms wanting client self-service portals (future, not shaping v1 UX).

## 5. Persona-driven design tensions (resolved)

1. **Мария wants control totals; Георги wants zero admin.** Resolution: all
   risk signals derive from data users already enter for their own benefit
   (next action, stages); no reporting-only fields exist.
2. **Иванка needs simplicity; Мария needs configurability.** Resolution:
   configuration (workflows, thresholds, labels) lives in settings screens
   only owners/managers see; daily screens carry zero configuration.
3. **Стоян's quiet months vs inactivity detection.** Resolution: a future-
   dated next action (e.g. hearing) suppresses inactivity warnings —
   deterministic rule I-4 in [13](13_DEADLINE_AND_REMINDER_ENGINE.md) §6.
