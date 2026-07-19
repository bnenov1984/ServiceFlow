# CS-03 — Glossary

Status: Draft · Bilingual by design: docs/code use the English term; UI and
generated documents use the Bulgarian term.

## Domain terms

| English (code) | Bulgarian (UI/legal) | Meaning |
|---|---|---|
| construction project | строеж / обект | The supervised construction, the aggregate root of everything. |
| construction category | категория на строежа | чл. 137 ЗУТ class I–VI; drives required documents and commissioning path. |
| building permit | разрешение за строеж (РС) | Permit no./date/issuer; the project's legal anchor. |
| client | възложител | Owner/developer ordering the construction. |
| builder | строител | Constructing firm; may be "по стопански начин" (self-build). |
| technical manager | технически ръководител | Builder's site manager (diploma-qualified). |
| designer | проектант | Design firm/person per project part; КИИП/КАБ registered. |
| consultant / supervisor | консултант / строителен надзор | The supervision firm (ДНСК удостоверение); our customer. |
| authors' supervision | авторски надзор | Designer's oversight during execution. |
| project part | част (СК, Ел, ВиК…) | Discipline: Архитектурна, Конструктивна, Електро, ВиК, Геодезия, ЕЕ, ПБ, ОВК. |
| act / protocol | акт / протокол (образец N) | A Наредба №3 form instance; each form is a distinct document type. |
| hidden works | скрити работи (обр. 12) | Works to be covered; must be accepted before covering. |
| structure acceptance | приемане на конструкцията (обр. 14) | The "груб строеж" gate. |
| handover act | констативен акт за годност (обр. 15) | Builder→client handover; precedes commissioning. |
| state acceptance commission | ДПК (обр. 16) | State commission, categories I–III. |
| order book | заповедна книга (обр. 4) | Running instruction log on site. |
| concrete log | дневник на бетоновите работи | Pour-by-pour concrete record. |
| final report | окончателен доклад (чл. 168 ал. 6 ЗУТ) | Consultant's closing report. |
| technical passport | технически паспорт | Наредба №5 document; parts А/Б/В. |
| commissioning | въвеждане в експлоатация | Удостоверение (IV–V) or разрешение за ползване (I–III). |
| cadastral identifier | идентификатор по КККР | dotted form, e.g. 12345.6789.101 (ПИ) / 12345.6789.101.1 (сграда) — synthetic example. |
| SMR (works) | СМР (строително-монтажни работи) | Construction and installation works. |
| bill/quantity line | количество (проектно/изпълнено) | Quantity pair with unit and assessment in act tables. |
| declaration of performance | декларация за експлоатационни показатели | Material certificate (CPR). |
| 72-hour test protocol | протокол за 72-часови проби ("акт 17" in practice) | Installation tests under operating conditions. |

## System terms

| Term | Meaning |
|---|---|
| knowledge base (KB) | The structured, provenance-carrying store of all project facts — the single source of truth. |
| fact | One authoritative value in the KB (typed, provenance-carrying, correction-tracked). See [21_PROVENANCE_AND_CONFIDENCE.md](21_PROVENANCE_AND_CONFIDENCE.md). |
| source document | An imported file (PDF/DOCX/scan) registered as evidence; never authoritative by itself. |
| document type | Registry entry describing one generatable/ingestable kind (e.g. `act_14`), with normative citation, practice aliases, template refs, rule set, workflow. |
| generated document | An instance of a document type produced by the pipeline; once issued, an immutable snapshot. |
| template manifest | The versioned, machine-readable binding/logic definition attached to a visual .docx template (ADR-CS-004). |
| binding | Manifest mapping from a template placeholder to a KB path/derivation. |
| extraction proposal | AI/parser output awaiting human confirmation; not a fact yet (ADR-CS-003). |
| finding | A rule-engine result: inconsistency, missing item, chronology violation; has severity and lifecycle. |
| phase gate | Workflow rule requiring documents/facts before a lifecycle transition (e.g. Act 14 needs the обр. 12/7/8 chain). |
| dossier | The ordered, complete set of a project's documents + index — the digital строително досие. |
| provenance | Source document, page/region, extraction method, confidence, and correction history attached to a fact. |
| issuance | The act of freezing a generated document (assign number/date, snapshot data, lock). |
