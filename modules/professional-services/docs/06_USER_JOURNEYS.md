# PS-06 — User Journeys

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Journeys reference personas (P-1…P-5, [05](05_PERSONAS_AND_STAKEHOLDERS.md))
and screens (S-1…S-10, [23](23_SCREEN_SPECIFICATIONS.md)). Steps marked ⚡ are
the moments the product must win (seconds, not minutes). Functional
requirements cite journeys as J-1…J-9.

## J-1 — Intake during a phone call (Иванка/Мария; the make-or-break journey)

1. Phone rings: a bank orders a valuation of an apartment in Варна. ⚡
2. S-3 New assignment: type client name → typeahead finds "Банка ДСК" (or
   offers inline creation with name+phone only).
3. Select service type "Оценка на недвижим имот" → the type's defaults load:
   workflow template, checklist template, document requirements.
4. Enter title ("Апартамент, ул. X, Варна"), official deadline (from the
   bank's order), owner (defaults per service type or current user).
5. Save. Assignment gets its number (АС-2026-0137), stage = first stage of
   the template, checklist and required documents instantiated; activity
   event recorded. Total time target: **<60 seconds**.
6. Immediately after save, the system prompts for the first next action
   (suggested: "Изискване на документи от клиента"). Accept or edit. ⚡

**Failure this journey kills:** P2 (forgotten assignment) — anything accepted
is in the register before the call ends.

## J-2 — Morning control ritual (Мария; daily, <5 minutes)

1. S-1 Dashboard: risk buckets in fixed order — Просрочени, За днес,
   Наближаващи, Без следваща стъпка, Блокирани, Без движение, Чакащи
   документи/клиент, Готови за предаване. ⚡
2. Click a bucket → filtered S-2 list; open worst case → S-4 details.
3. For each intervention: reassign, add/replace next action, call the client
   (log it in 2 clicks from the assignment), or extend a deadline (reason
   required, historised).
4. Workload glance (S-9): who is overloaded, who can take the new intake.

**Product promise:** after this ritual, zero silent risks remain — every red
item was either acted on or consciously snoozed (visible as acknowledged).

## J-3 — Executing an assignment (Георги; continuous)

1. "Моята работа" filter on S-2 (or dashboard "my" toggle): his assignments
   sorted by next-action due, then official deadline.
2. Opens assignment → does the next action (e.g. schedules the inspection).
3. Completes the next action ⚡ → completion dialog *requires* choosing:
   enter the new next action | mark stage transition | explicitly leave
   without one (recorded as deliberate, shows in no-next-action bucket).
4. Ticks checklist items as work proceeds; uploads photos to dossier
   (category: снимки от оглед); logs the client call about access.
5. Stage advances (Оглед извършен → Пазарни аналози) — one click on S-4.

## J-4 — Chasing missing documents (Иванка; the stall-breaker)

1. Dashboard bucket "Чакащи документи" → assignments in
   `waiting_documents`-category stages or with missing document requirements.
2. Opens assignment: requirement list shows Скица — липсва, Нотариален акт —
   изискан на 14.07.
3. Calls the client; logs communication (type: обаждане, direction: изходящо,
   note "обеща скицата до петък") ⚡; sets next action "Проверка за скица",
   due петък.
4. Document arrives by email → uploads file, links it to the requirement →
   requirement becomes получен; if all requirements received, system suggests
   stage transition (e.g. to Готово за стартиране).

## J-5 — Delivery, corrections, close-out (Мария/Георги)

1. Draft ready → stage Вътрешна проверка; reviewer (Мария) checks; found
   issues → stage back to work-category stage with next action "Корекции по
   раздел 3" assigned to Георги.
2. Approved → Готово за предаване → delivered: record delivery info (how,
   to whom, date), lifecycle state → `delivered`; delivered file goes to
   dossier category "предадени".
3. Payment entry recorded (or invoice noted); when nothing further is
   expected → `completed` (completion date, actor recorded, audit event).
4. Client calls two weeks later wanting an update to the report → **new
   linked follow-up assignment** (ADR-PS-012), pre-filled from the original;
   the completed one stays immutable.

## J-6 — Court expertise long-wait handling (Стоян)

1. Appointment received → assignment created with court, case number,
   questions (typed JSONB details), submission deadline, hearing date.
2. Submits opinion (stage Предадено в съда) → next action becomes the
   hearing (appointment-flagged, due = hearing date, months away).
3. The assignment stays quiet **without** triggering inactivity warnings
   (future-dated appointment suppresses staleness — rule I-4).
4. Week before hearing: attention warning surfaces it; after the hearing he
   marks attended → prompted: complete, or follow-up (допълнителна
   експертиза) as a linked assignment.

## J-7 — New service type & workflow setup (Мария; rare, must be doable alone)

1. S-7 Service types: creates "Пазарна оценка на МПС", reorders list.
2. S-8 Workflow configuration: copies the default template, renames stages,
   removes two, adds "Проверка в КАТ" (category: work); attaches template
   and a checklist template to the new service type.
3. Existing assignments are untouched (templates are copied onto assignments
   at creation — [12](12_WORKFLOW_AND_STATUS_MODEL.md) §5); new intake uses
   the new stages.

## J-8 — Monthly financial glance (Мария + П-5 accountant)

1. S-2 list filtered: state delivered/completed, month, with agreed /
   invoiced / paid / outstanding columns; totals row.
2. Accountant (readonly + financial visibility) exports/reads the same list;
   flags unpaid deliveries; Мария sets next actions "Напомняне за плащане".

## J-9 — Onboarding an empty organisation (Мария; first 30 minutes)

1. Tenant provisioned (platform, Етап-3 flow); module active; owner logs in.
2. Guided empty states: create first service type (or accept the shipped
   starter set: Оценка, Експертиза, Строителни актове, Консултация — each
   with its example workflow + checklist from [../examples/](../examples/)),
   add users, set org label for "Assignment", confirm warning thresholds.
3. Enters 3 real assignments from her Excel; dashboard already meaningful.
   **No import tool in MVP** — 30–150 rows are enterable by hand; a CSV
   import is post-MVP ([34](34_MVP_DEFINITION.md)).

## Journey → requirement traceability

Each ⚡ step and each journey outcome is mapped to FR ids in
[38_TRACEABILITY_MATRIX.md](38_TRACEABILITY_MATRIX.md). Journeys J-1, J-2,
J-3 are the acceptance backbone: MVP is not done until all three run
end-to-end ([37](37_ACCEPTANCE_CRITERIA.md)).
