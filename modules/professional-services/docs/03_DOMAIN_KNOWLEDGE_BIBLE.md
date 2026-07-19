# PS-03 — Domain Knowledge Bible

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

What the module must *know* about how small Bulgarian professional-service
firms actually work. Sources: PO domain input (construction supervision,
valuation, court expertise practice), Bulgarian procedural rules as they shape
deadlines, and the three worked examples in [../examples/](../examples/).
Regulatory citations are context, not implemented rules — the module never
computes statutory terms itself in MVP (see §6).

## 1. The three reference service lines

### 1.1 Court expertise (съдебна експертиза)

- **Intake:** the expert receives a court appointment (определение) naming
  the case (court, case number, year), the questions (задачи на
  експертизата), and a deposit (депозит) amount. Acceptance is largely
  non-optional for listed experts; declining requires grounds.
- **Key dates:** submission deadline — commonly "не по-късно от 7 дни преди
  съдебното заседание" (ГПК чл. 199); the hearing date (съдебно заседание)
  itself; deposit payment date (work often should not start before it).
- **Flow:** appointment → case materials review (материали по делото) →
  deposit check → on-site inspection (оглед) if needed → measurements/
  calculations → draft opinion (заключение) → submission to court →
  hearing attendance (защита на заключението) → possibly допълнителна or
  повторна експертиза (a *new* assignment, linked — see ADR-PS-012).
- **Pain specifics:** hearings scheduled months out (long quiet periods —
  inactivity detection must not cry wolf: the hearing *is* the next action);
  fines for late submission; multiple simultaneous appointments from
  different courts.

### 1.2 Real-estate valuation (оценка на недвижим имот)

- **Intake:** order from a bank (mortgage), a company (financial reporting),
  a court/bailiff (изпълнително дело), or a private client. Banks impose
  short SLAs (3–5 working days is common) and their own report formats.
- **Inputs to chase:** ownership document (нотариален акт), cadastral sketch
  (скица/схема от КККР), tax valuation (данъчна оценка), building
  documentation for special cases. Missing inputs are the #1 delay.
- **Flow:** request → documents collection → inspection appointment → market
  research (сравними имоти) → calculations (comparative/income/cost methods)
  → report drafting → internal review (four-eyes for certified valuers) →
  delivery → payment. Certified per ЗНО (Камара на независимите оценители);
  reports carry the valuer's certificate number.
- **Pain specifics:** high volume, short cycles (days, not months), many
  simultaneous small assignments — the table view, not Kanban, is the natural
  cockpit; repeat institutional clients (banks) with monthly invoicing.

### 1.3 Construction acts service (актове по Наредба №3 / технически паспорт)

- **Intake:** an investor or builder engages a supervision firm to prepare
  and shepherd the statutory acts (обр. 2…17), technical passport, and final
  report for a construction project.
- **Flow:** engagement → receipt of design documentation → documentation
  review → identify missing documents → prepare acts → internal review →
  signature collection (the notorious stall: many signatories) → delivery.
- **Pain specifics:** months-long engagements; progress driven by the *site's*
  schedule, not the firm's; long "waiting for signatures" states that need
  follow-up nudges; one engagement generates dozens of sub-deliverables. The
  *content* of the acts belongs to the Construction Documentation module —
  this module tracks the engagement wrapper
  ([29_CONSTRUCTION_DOCUMENTATION_INTEGRATION.md](29_CONSTRUCTION_DOCUMENTATION_INTEGRATION.md)).

## 2. Cross-cutting domain facts

- **The assignment is the unit of commerce and of liability.** One client may
  have many concurrent assignments of different types; the assignment, not
  the client, has the deadline, price, and dossier.
- **Two deadline regimes coexist:** an *official* deadline with external
  force (court, bank, contract) and an *internal* target the firm sets to
  protect itself. The internal one should normally precede the official one;
  the gap is the firm's safety margin. They must never be one field.
- **Waiting is half the lifecycle.** Waiting-for-documents, -client,
  -deposit, -signatures, -hearing are normal, potentially long states. The
  operational question in a waiting state is not "who is working?" but "who
  chases, and when do we chase again?" — hence next actions exist in waiting
  states too (follow-up actions).
- **Appointments are their own thing.** An inspection (оглед) or hearing is
  a fixed calendar moment, not a deadline: missing it usually costs a
  rescheduling cycle, not a breach — but it anchors preparation actions.
- **Documents are inputs before they are outputs.** Every service line
  begins with collecting client/institution documents. "Required vs received
  vs missing" must be explicit per assignment ([17_DOCUMENT_DOSSIER.md](17_DOCUMENT_DOSSIER.md)).
- **Delivery ≠ completion.** Delivered work may await client confirmation,
  corrections, a hearing, or payment. Firms close an assignment when nothing
  further is expected — often weeks after delivery.
- **Payment realities:** court deposits paid to the court, not the expert
  (released later); bank valuations invoiced monthly in bulk; private
  clients pay advance + remainder on delivery. MVP models money as amounts
  on the assignment, not as an invoicing system ([21_FINANCIAL_BOUNDARIES.md](21_FINANCIAL_BOUNDARIES.md)).
- **Vocabulary is firm-specific.** The same object is a поръчка (valuers),
  дело/експертиза (experts), преписка/досие (administrative), обект/договор
  (supervision). Hence the configurable visible label over one internal term
  (ADR-PS-004).

## 3. Time and calendar knowledge

- Operating timezone: **Europe/Sofia** (EET/EEST, DST transitions in March
  and October). All date-only deadlines mean "end of that day in
  Europe/Sofia" ([13_DEADLINE_AND_REMINDER_ENGINE.md](13_DEADLINE_AND_REMINDER_ENGINE.md)).
- Bulgarian public holidays are fixed-list per year plus Orthodox Easter
  (movable) and the ЗУТ-relevant carry-over rule (holidays falling on
  weekends generate compensatory Mondays, set annually by the Council of
  Ministers). The module ships a per-year holiday table as **data**; MVP uses
  it for *display and warnings only* — never to move a deadline (ADR-PS-008).
- Statutory terms (срокове) in ГПК/АПК count in days/weeks with their own
  rules (e.g. term ending on a non-working day extends to the next working
  day — ГПК чл. 60). MVP does **not** compute statutory terms; the user
  enters the resulting date. Deferred: a term calculator, only if firms ask.

## 4. What the domain does *not* need (negative knowledge)

- No stock, parts, or physical intake/return — there is no physical asset in
  custody (the sharpest difference from ServiceFlow).
- No diagnosis/approval commercial gate — professional engagements are
  agreed up front; changes are new agreements, not approval workflows.
- No shift/rota planning; no billable-hours timesheets in MVP (valuers and
  experts price per assignment, not per hour).
- No cross-firm collaboration (subcontracted experts are recorded as team
  notes, not as platform users).

## 5. Volume and shape assumptions (sizing, not promises)

- Assignments per firm-year: 30 (supervision) … 1500 (high-volume valuers).
- Concurrent active: 10–150. Files per assignment: 5–100, mostly PDFs/photos.
- Users per firm: 1–15. One organisation = one legal firm (tenant).
- These fit comfortably in the platform's existing Postgres + RLS model; no
  special scale work needed (26_BUSINESS_RULES.md keeps derived counters
  recomputable rather than cached).

## 6. Regulatory boundary statement

The module records dates, documents, and money as **facts entered by the
firm**. It does not interpret ГПК/ЗУТ/ЗНО, does not certify compliance, and
does not compute statutory deadlines in MVP. This keeps legal risk with the
professional (where it legally sits anyway) and keeps the engine
deterministic and small.
