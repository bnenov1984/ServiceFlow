# PS-04 — Glossary and Terminology

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Internal (code/docs) terms are English and **stable**; user-facing terms are
Bulgarian and, for the core object, **configurable per organisation**
(ADR-PS-004). Terms here are the single vocabulary for all PS documents; the
consistency review checks every other document against this list.

## 1. Core objects

| Internal term | Default BG UI term | Definition |
|---|---|---|
| **Assignment** | Поръчка (configurable: Възлагане, Казус, Досие, Преписка, Проект, Експертиза, Оценка, Задача*) | Work accepted from a client: the aggregate root carrying owner, deadlines, workflow position, dossier, money. *"Задача" as org label is allowed but discouraged (collides with Task); settings UI warns. |
| **Client** | Клиент | Person or organisation the firm works for (court, bank, company, municipality, individual). Owned by this module (ADR-PS-003). |
| **Client contact** | Лице за контакт | Named person at a client organisation. |
| **Service type** | Вид услуга | Org-configurable classification of assignments (Оценка на имот, Съдебна експертиза, …); may carry defaults (workflow template, checklist template). |
| **Lifecycle state** | Състояние | Fixed, code-owned coarse state of an assignment: `active`, `delivered`, `completed`, `cancelled`. Invariants and permissions hang here ([12](12_WORKFLOW_AND_STATUS_MODEL.md)). |
| **Workflow template** | Работен процес (шаблон) | Org-configurable ordered set of stages, optionally bound to a service type. |
| **Stage** | Етап | A step in a workflow template (e.g. Оглед насрочен). An assignment is at exactly one stage while `active`/`delivered`. The user-visible "status" of daily speech. |
| **Stage category** | Категория на етап | Code-owned classification of every stage: `work`, `waiting_client`, `waiting_documents`, `review`, `delivery`. Powers dashboards and inactivity rules deterministically. |
| **Next action** | Следваща стъпка | The single open "what happens next": description + owner + due date (+ optional reminder / blocking note). At most one open per assignment ([14](14_NEXT_ACTION_MODEL.md)). |
| **Task** | Задача | A unit of work inside an assignment: title, assignee, due date, done. |
| **Checklist item** | Точка от чеклист | A Task of kind `checklist`, typically instantiated from a template; same table, same mechanics ([15](15_TASKS_AND_CHECKLISTS.md)). |
| **Checklist template** | Шаблонен чеклист | Org-level named list of checklist items, attachable to a service type. |
| **Document requirement** | Изискуем документ | A named input document the assignment needs: `missing` → `requested` → `received` (or `waived`) ([17](17_DOCUMENT_DOSSIER.md)). |
| **Dossier file** | Файл / Документ | An uploaded file in the assignment dossier, categorised (incoming, working, photos, calculations, draft, delivered, signed, invoice, correspondence, other). |
| **Communication entry** | Комуникация | Manually logged contact event: call, email, meeting, visit, court communication, message, internal note, document request, delivery confirmation ([18](18_COMMUNICATION_LOG.md)). |
| **Activity event** | Събитие / История | Append-only record of every meaningful change on an assignment; drives `last_activity_at` ([30](30_SECURITY_PRIVACY_AND_AUDIT.md)). |
| **Payment entry** | Плащане / Разход | Money fact on an assignment: advance, payment, expense, invoiced-amount record ([21](21_FINANCIAL_BOUNDARIES.md)). |

## 2. Dates and deadlines (never one generic field — see [13](13_DEADLINE_AND_REMINDER_ENGINE.md))

| Internal term | Default BG UI term | Definition |
|---|---|---|
| **Official deadline** | Краен срок | Externally binding delivery date (court, bank, contract). Date-only by default; optional exact time. Changes require a reason and are historised. |
| **Internal target** | Вътрешен срок | Firm-set target preceding the official deadline; the safety margin. |
| **Received date** | Дата на получаване | When the assignment was accepted. |
| **Planned start** | Планиран старт | When work is intended to begin. |
| **Next-action due** | Срок на следващата стъпка | Due date of the open next action. |
| **Task due** | Срок на задача | Due date of an individual task/checklist item. |
| **Appointment** | Насрочена дата (оглед, заседание) | Fixed calendar moment (inspection, hearing, meeting); anchors preparation, is not itself a breach-deadline. Modelled as a next action or task flagged `is_appointment`, not a third date system. |
| **Reminder** | Напомняне | A date on which the module notifies regardless of due state. |
| **Payment due** | Срок за плащане | When outstanding money is expected. |

## 3. Risk & warning vocabulary (deterministic labels — never colour-only)

| Internal | BG UI | Meaning (defaults; thresholds org-configurable) |
|---|---|---|
| `normal` | В срок | >7 days to the relevant deadline |
| `attention` | Наближаващ срок | ≤7 days |
| `urgent` | Спешно | ≤3 days |
| `critical` | Днес | due today |
| `breached` | Просрочено | past deadline, assignment not delivered/completed |
| `stale` | Без движение | no activity ≥5 working days on an active assignment |
| `no_next_action` | Без следваща стъпка | active assignment with no open next action |
| `blocked` | Блокирано | open next action carries a blocking reason |
| `never_started` | Незапочната | active, still at first stage, no activity since creation threshold |
| `undelivered_closeout` | Недоприключена | delivered but not completed for ≥N days |

## 4. Terminology rules

1. Internal names never change when an org changes its visible label; i18n
   keys use the internal term (`ps.assignment.*`), and the catalog renders the
   org's label wherever the generic word appears.
2. "Status" is banned in code and docs as an entity name — use *lifecycle
   state* or *stage* explicitly (the №1 ambiguity risk found in analysis).
3. "Deadline" unqualified is banned — always *official deadline*, *internal
   target*, *task due*, *next-action due*, etc.
4. "Case"/"Дело" is reserved for court cases inside court-expertise data,
   never for the Assignment itself.
5. ServiceFlow vocabulary (order, asset, diagnosis, intake) must not appear
   in this module's UI or schema.

## 5. Deliberate divergences from ServiceFlow terms

| ServiceFlow | This module | Why different |
|---|---|---|
| ServiceOrder | Assignment | no physical asset, no repair semantics; different lifecycle |
| Customer | Client | institutional clients (courts, banks) are first-class; different fields, different duplicate rules |
| Status (seeded global list, frozen matrix) | Lifecycle state + Stage | configurability requirement makes one flat list unworkable ([12](12_WORKFLOW_AND_STATUS_MODEL.md)) |
| ContactRecord | Communication entry | richer typed log with direction; no repair "note" duality |
| Timeline | Activity events | same *pattern*, module-owned implementation (BOS-02 group D rule) |
