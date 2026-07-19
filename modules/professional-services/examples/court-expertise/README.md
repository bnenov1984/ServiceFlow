# Worked example A — Court Expertise (Съдебна експертиза)

Validates against [../../schemas/](../../schemas/); narratively exercises
PS-09…PS-14. Persona: Стоян (P-4), solo court expert.

## 1. Starter workflow template (seeded with the service type)

```json
{
  "name": "Съдебна експертиза",
  "stages": [
    {"name": "Получено определение",        "category": "work"},
    {"name": "Преглед на материалите",      "category": "work"},
    {"name": "Чакане на депозит",           "category": "waiting_client"},
    {"name": "Насрочен оглед",              "category": "work"},
    {"name": "Извършен оглед",              "category": "work"},
    {"name": "Измервания и изчисления",     "category": "work"},
    {"name": "Изготвяне на заключение",     "category": "work"},
    {"name": "Вътрешна проверка",           "category": "review"},
    {"name": "Предадено в съда",            "category": "delivery"},
    {"name": "Предстоящо заседание",        "category": "waiting_client"}
  ]
}
```

(The commissioned example's "Appointment Received … Completed" list maps
1:1; its "Completed" is the lifecycle state, not a stage — PS-12 §3.)

Starter checklist template (kind `checklist`): определение получено ·
въпросите прегледани · депозит проверен · материали по делото прегледани ·
оглед извършен · измервания извършени · изчисления готови · отговори
изготвени · заключение предадено · заседание посетено.

Default document requirements: Определение за назначаване · Материали по
делото · Доказателство за внесен депозит.

## 2. The assignment (day 1)

```json
{
  "number": "ЕКС-2026-0031",
  "title": "СТЕ по гр.д. 4211/2026, РС Варна — пазарна стойност на апартамент",
  "client_id": "⟨Районен съд — Варна (organization)⟩",
  "service_type_id": "⟨Съдебна експертиза⟩",
  "owner_user_id": "⟨Стоян⟩",
  "priority": "normal",
  "lifecycle_state": "active",
  "received_on": "2026-07-06",
  "internal_target_on": "2026-09-04",
  "official_deadline_on": "2026-09-08",
  "details_kind": "court_expertise",
  "details": {
    "v": 1,
    "court": "Районен съд — Варна",
    "case_number": "4211", "case_year": 2026, "case_type": "гражданско",
    "questions": [
      "Каква е пазарната стойност на самостоятелен обект с ид. 10135.2560.123.1.17 към датата на огледа?",
      "Какъв е размерът на подобренията, извършени след 2020 г.?"
    ],
    "deposit_amount": "400.00", "deposit_status": "pending",
    "hearing_on": "2026-09-15", "inspection_required": true
  },
  "agreed_price": "400.00", "currency": "BGN"
}
```

Official deadline = submission term (7 дни преди заседанието на 15.09,
entered by Стоян — the module computes no statutory terms, ADR-PS-008 §6);
internal target 4 дни по-рано — his margin. First next action after
intake: „Проверка дали депозитът е внесен" — owner Стоян, due 13.07.

## 3. Timeline of model behaviours the example proves

| Date | Event | Model behaviour exercised |
|---|---|---|
| 06.07 | intake | number, stage copy, checklist + requirements instantiated (AC-1) |
| 13.07 | deposit still unpaid → next action replaced: „Молба до съда за депозита", blocking_reason: „не започвам преди депозит" | N-5 supersede + N-6 `blocked` signal, stage stays Чакане на депозит (waiting_client) |
| 21.07 | deposit paid (communication: court letter, incoming) → stage Насрочен оглед; next action = appointment: „Оглед на имота", due 29.07, `is_appointment` | requirement flow, stage transition, N-7 |
| 29.07–20.08 | inspection, measurements, drafting; checklist ticks; photos uploaded (category `photos`) | J-3 loop, dossier |
| 21.08 | заключение предадено в съда (stage Предадено в съда → lifecycle `delivered`, delivery: „деловодство РС Варна") | delivery-category prompt (BR-3→BR-2 chain) |
| 21.08→15.09 | next action = appointment „Заседание", due 15.09 — assignment quiet, **no staleness warnings** | I-4 suppression — the Стоян tension resolved (PS-05 §5.3) |
| 08.09 | attention window for the hearing appointment surfaces it | risk stream on next-action due |
| 15.09 | hearing attended → complete; fee paid entry recorded | close-out, INV-7 |
| 03.10 | court orders допълнителна СТЕ → **new linked assignment** ЕКС-2026-0044 (`follow_up_of`), fresh deadlines | ADR-PS-012 |
