# Worked example B — Real Estate Valuation (Оценка на недвижим имот)

Persona: Мария's four-person valuation firm (P-1, P-2), high volume, bank
SLAs. Exercises the fast-cycle path: J-1 intake ⚡, J-4 document chase,
internal review, money-light.

## 1. Starter workflow template

```json
{
  "name": "Оценка на недвижим имот",
  "stages": [
    {"name": "Нова заявка",           "category": "work"},
    {"name": "Чакане на документи",   "category": "waiting_documents"},
    {"name": "Насрочен оглед",        "category": "work"},
    {"name": "Извършен оглед",        "category": "work"},
    {"name": "Пазарни аналози",       "category": "work"},
    {"name": "Изчисления",            "category": "work"},
    {"name": "Изготвяне на доклад",   "category": "work"},
    {"name": "Вътрешна проверка",     "category": "review"},
    {"name": "Готов за предаване",    "category": "delivery"}
  ]
}
```

Starter checklist: нотариален акт получен · скица/схема получена · оглед
насрочен · оглед извършен · аналози събрани · изчисления готови · доклад
изготвен · вътрешна проверка минала · доклад предаден. (Matches the
commissioned valuation checklist; the two document items also exist as
requirements — the seeds keep checklist vs requirements disjoint per
PS-15 §4, so the shipped checklist drops those two and the requirements
carry them. Recorded so the seed content is built correctly.)

Default requirements: Нотариален акт · Скица/схема от КККР · Данъчна
оценка (waivable — not every purpose needs it).

## 2. The assignment (created during the bank's phone call — 55 seconds)

```json
{
  "number": "ОЦ-2026-0137",
  "title": "Апартамент, ул. Дебър 11, Варна — обезпечение",
  "client_id": "⟨Банка ДСК АД (organization)⟩",
  "client_contact_id": "⟨Ив. Петрова, кредитен инспектор⟩",
  "service_type_id": "⟨Оценка на недвижим имот⟩",
  "owner_user_id": "⟨Георги⟩",
  "priority": "high",
  "lifecycle_state": "active",
  "received_on": "2026-07-14",
  "internal_target_on": "2026-07-17",
  "official_deadline_on": "2026-07-20",
  "payment_due_on": "2026-08-31",
  "details_kind": "valuation",
  "details": {
    "v": 1,
    "property_address": "гр. Варна, ул. Дебър 11, ет. 3, ап. 7",
    "property_kind": "апартамент",
    "cadastral_id": "10135.1508.211.2.7",
    "purpose": "обезпечение по ипотечен кредит",
    "orderer_ref": "заявка 2026-ВН-4415",
    "inspection_on": null
  },
  "agreed_price": "180.00", "currency": "BGN"
}
```

Note the compressed timeline (6 calendar days) — the same engine that
watches Стоян's two-month expertise runs a 6-day SLA: 20.07 deadline means
`attention` **immediately** (≤7 days at creation), which is correct and
useful, not noise: bank orders live their whole life in the attention band,
and the firm's control question is the *internal* target (17.07) + next
actions.

## 3. Behaviours the example proves

| When | What | Model point |
|---|---|---|
| 14.07 12:05 | intake ⚡; requirements auto-missing; next action „Изискване на документи от банката", due same day | AC-1; J-1 |
| 14.07 16:40 | documents e-mailed; uploads (category `incoming`), linked to requirements → received; sketch missing → stage Чакане на документи; next action „Позвъняване за скицата", due 15.07 | J-4; [17] §1 |
| 15.07 | скица received; system suggests stage transition (all requirements received) — Мария confirms Насрочен оглед; appointment next action „Оглед", due 16.07 09:30 | suggestion-not-automation (PS-12 §6) |
| 16.07 | inspection; photos from phone (narrow-screen upload); checklist ticks | NFR-PS-20 |
| 17.07 | Георги finishes draft → Вътрешна проверка; next action owner = Мария („Преглед на доклада") — action owner ≠ assignment owner | [14] §1 |
| 17.07 | Мария returns corrections: stage back to Изготвяне на доклад with note; next action to Георги | backward-move soft guard (BR-3) |
| 18.07 | delivered by email to the bank → `delivered`; report PDF category `delivered` | J-5 |
| 31.08 | no payment → `payment_overdue` fires to managers; J-8 glance shows it | [21] §2 |
| 05.09 | bank pays (monthly batch); payment entry; complete | close-out |

Volume corollary: with ~120 such assignments live, Мария's cockpit is the
**table** sorted by internal target, not Kanban — the [22] §3 verdict this
persona drove.
