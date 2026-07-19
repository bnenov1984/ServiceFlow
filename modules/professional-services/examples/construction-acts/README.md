# Worked example C — Construction Acts (Строителни актове)

Persona: supervision firm (P-2 Георги as responsible engineer). The
months-long, waiting-heavy engagement — and the Construction Documentation
integration case (PS-29). This module tracks the **engagement wrapper**;
the acts' *content* belongs to the CS module.

## 1. Starter workflow template

```json
{
  "name": "Строителни актове",
  "stages": [
    {"name": "Нов ангажимент",          "category": "work"},
    {"name": "Получени проекти",        "category": "work"},
    {"name": "Преглед на документацията","category": "review"},
    {"name": "Липсваща документация",   "category": "waiting_documents"},
    {"name": "Изготвяне на актове",     "category": "work"},
    {"name": "Вътрешна проверка",       "category": "review"},
    {"name": "Чакане на подписи",       "category": "waiting_client"},
    {"name": "Предадени",               "category": "delivery"}
  ]
}
```

Starter checklist: договор подписан · проектна документация получена ·
преглед извършен · актове изготвени · вътрешна проверка минала · подписи
събрани · комплект предаден.

Default requirements: Разрешение за строеж · Одобрени проекти (по части) ·
Договор за надзор.

## 2. The assignment

```json
{
  "number": "СН-2026-0009",
  "title": "Актове обр. 14 и 15 — жилищна сграда, кв. Аспарухово",
  "client_id": "⟨Хоум Инвест ЕООД (organization, инвеститор)⟩",
  "service_type_id": "⟨Строителни актове⟩",
  "owner_user_id": "⟨Георги⟩",
  "priority": "normal",
  "lifecycle_state": "active",
  "received_on": "2026-06-01",
  "internal_target_on": "2026-10-15",
  "official_deadline_on": "2026-10-30",
  "details_kind": "construction_acts",
  "details": {
    "v": 1,
    "project_name": "Жилищна сграда с гаражи, УПИ III-211, кв. Аспарухово",
    "site": "гр. Варна, кв. Аспарухово",
    "permit_ref": "РС-114/12.03.2025, Община Варна",
    "investor_name": "Хоум Инвест ЕООД",
    "required_acts": ["обр. 14", "обр. 15"],
    "responsible_engineer_user_id": "⟨Георги⟩"
  },
  "agreed_price": "2400.00", "currency": "BGN"
}
```

## 3. Behaviours the example proves

| When | What | Model point |
|---|---|---|
| 01.06 | intake; team member added (втори инженер) | FR-PS-022 |
| 09.06 | documentation review finds missing part Електро → stage Липсваща документация; requirement added ad hoc; next action „Изискване на част Електро от проектанта", due 16.06 | ad-hoc requirements ([17] §1); the chase pattern |
| 16.06→30.06 | investor silent; next action overdue → I-3 badge + notification; after 2 days escalation to managers; call logged 24.06 („обеща до 1.07") with combined log+new-action flow | N-3, [19] §4, [18] §2 |
| 08.07 | docs arrive; acts drafting; **if CS module active:** S-4 Връзки → link to CS project „УПИ III-211" — acts content produced there; PS shows deliverables read-only | PS-29 link; no file copying |
| 20.09 | acts to signing → Чакане на подписи (waiting_client); next action „Обаждане до инвеститора за подписите", due 27.09 | waiting + chase (PS-14 §4) |
| 13.10 | 10 working days in waiting → I-5 `waiting_too_long` joins the dashboard | deterministic stagnation |
| 21.10 | signed; delivered (протоколно предаване); state `delivered` | J-5 |
| 30.10 | official deadline passes with state delivered ⇒ **no breach** | [11] §5; T-12 edge 1 |
| 04.11 | final payment; complete. Spring 2027: next acts batch → follow-up assignment linked to the **same CS project** | ADR-PS-012 + PS-29 §2 cardinality |

## 4. The three-example proof (PS-09 §4)

Same tables, same engine, zero code branches by service type beyond the
typed `details` schema: a 6-day bank SLA (B), a two-month court term with
a silent waiting period (A), and a five-month waiting-heavy engagement
with cross-module production (C) — all expressed by configuration
(templates, checklists, requirements) over one generic Assignment.
