# CS-02 — Domain Knowledge Bible

Status: **Draft — regulatory citations must be verified against current
normative texts before any template is declared authoritative** (see §8).
Date: 18.07.2026. Sources: ЗУТ, Наредба №3/31.07.2003, Наредба №5/28.12.2006,
and the real sample set from a supervision firm ([samples/](../samples/README.md)).

## 1. Regulatory frame

- **ЗУТ (Закон за устройство на територията)** — the Spatial Development Act.
  Key articles for this domain: чл. 137 (construction categories I–VI),
  чл. 160–168 (participants and their duties; чл. 166–168 define the
  консултант/строителен надзор), чл. 169 (essential requirements), чл. 176
  (констативен акт при завършване), чл. 177 (въвеждане в експлоатация).
- **Наредба №3/2003 за съставяне на актове и протоколи по време на
  строителството** — defines the numbered act forms (образци). The forms are
  annexes to чл. 7, ал. 3 (e.g. Act 14 is "Приложение №14 към чл. 7, ал. 3,
  т. 14" — visible verbatim in the sample).
- **Наредба №5/2006 за техническите паспорти на строежите** — defines the
  technical passport structure (Части А/Б/В with numbered sections;
  the sample follows чл. 8's приложение).
- **Наредба №1/2003 за номенклатурата на видовете строежи** — category detail.
- Supporting regime: Наредба №2/2003 (заповедна книга is обр. 4), ПИПСМР/БДС
  standards for concrete works (дневник на бетоновите работи), Наредба
  №Iз-1971/2009 (fire safety), кадастрална система (КККР identifiers).

## 2. Construction categories and why they matter

чл. 137 ЗУТ classes constructions I (highest) … VI. Supervision is mandatory
for categories I–IV and for parts of V; commissioning differs:

- **I–III**: Разрешение за ползване issued by ДНСК after a state acceptance
  commission (ДПК, протокол обр. 16).
- **IV–V**: Удостоверение за въвеждане в експлоатация from the municipality,
  based on the consultant's окончателен доклад — no ДПК.

The sample project is category V (ал. 1, т. 5а чл. 137) — the MVP's home
turf. Category drives *which* documents are required — a first-class rules
input ([13_RULES_ENGINE.md](13_RULES_ENGINE.md)).

## 3. Participants (чл. 160 ЗУТ) — the recurring cast

| Role | BG | Key attributes (all seen in samples) |
|---|---|---|
| Client/owner | Възложител | name(s), co-ownership, address |
| Builder | Строител | firm, ЕИК, ЦПРС registration, представител; **or** "по стопански начин" (self-build, seen in Act-17 sample) |
| Technical manager | Технически ръководител | person, diploma no./series/issuer/specialty, appointment order (заповед на строителя) |
| Designer(s) | Проектант | firm + per-part persons: КИИП/КАБ рег. №, ПППр (full design capacity) |
| Consultant (supervision) | Консултант / строителен надзор | firm, ЕИК, ДНСК удостоверение № + validity, управител, per-part specialists from the МРРБ-заверен списък |
| Authors' supervision | Авторски надзор | designer signing during execution |

Observations that shape the model:
- The *same* person appears in many roles across documents (проектант част СК
  signs Act 7/8/12/14; надзорникът signs almost everything) → participants are
  project-level entities referenced by documents, never re-typed
  ([07_DOMAIN_MODEL.md](07_DOMAIN_MODEL.md)).
- Attributes have validity windows (a ДНСК удостоверение is valid to a date;
  builder changed mid-project in the sample, with обр. 10/11 marking the
  stop/resume) → participation is time-bounded.
- Project parts (части): Архитектурна, Конструктивна (СК), Електро, ВиК,
  Геодезия, ЕЕ, ПБ, ОВК… — both designers and supervision specialists are
  organized per part; acts are often per part ("Част: СК" in every combined-
  file header).

## 4. The document universe (evidence-based)

### 4.1 Observed directly in the samples

| Form | Name (abbreviated) | Role in lifecycle | Sample evidence |
|---|---|---|---|
| Обр. 2 | Откриване на строителна площадка, строителна линия и ниво | start of construction | referenced in Act 14/15 inventories |
| Обр. 3 | Съответствие на строежа със строителните книжа; приложен ПУП | early check | referenced |
| Обр. 4 | Заповедна книга | running order book | referenced ("Заповедна книга №1/…") |
| Обр. 5 | Уточняване на терена, основен репер | site setout | referenced |
| Обр. 6 | Приемане на земната основа и коти на изкопа | foundations gate | referenced |
| **Обр. 7** | Приемане на СМР по нива и елементи на конструкцията | per structural level | full instances in combined file |
| **Обр. 8** | Състояние на декофрирания бетон (приемане на бетонни/стоманобетонни работи) | after each pour's formwork strip | full instances in combined file |
| Обр. 10 | Състояние при спиране на строителството | suspension | referenced (builder change) |
| Обр. 11 | Състояние при продължаване | resumption | referenced |
| **Обр. 12** | Всички видове СМР, подлежащи на закриване (скрити работи) | before covering any work | full instances (СК, Ел, ВиК, Арх variants) |
| **Обр. 14** | Приемане на конструкцията | structure acceptance gate | dedicated template + filled instance |
| **Обр. 15** | Годност за приемане на строежа | builder→client handover, pre-commissioning | dedicated template + filled instance |
| "Акт 17" (practice name) | 72-часови проби при експлоатационни условия (ВиК, Ел variants) | installations testing | dedicated templates |
| — | Технически паспорт (Наредба №5) | commissioning + operation | dedicated template + filled instance |
| — | Дневник на бетоновите работи | concrete log | referenced by обр. 8/12/14 |
| — | Протоколи за контрол (заземяване, мълниезащита, импеданс…) + декларации за експлоатационни показатели | material/installation certificates | itemized in Act 15 & passport |

### 4.2 Known from the regime, no sample yet

Обр. 16 (ДПК protocol, categories I–III), обр. 17 in its *normative* meaning,
окончателен доклад по чл. 168 ал. 6, energy efficiency certificate,
екзекутивна документация. These stay out of MVP until samples exist
(evidence rule, CS-01 §3.6).

### 4.3 Naming hazard (important)

Practice numbering diverges from normative numbering: the firm's "акт-17"
files are 72-hour installation test protocols, while Наредба №3's обр. 17 is
a different form. **Conclusion: the document-type registry is data, keyed by
an internal type id, carrying both normative citation and practice aliases**
(ADR-CS-007). Never hard-code "act number" semantics.

## 5. The lifecycle as the samples tell it

```
Permit (РС) → обр.2 (line & level) → обр.4 (order book opened)
  → обр.5 (setout) → обр.6 (excavation/founding) → [обр.3 conformity]
  → per pour, repeated up the building:
        обр.12 (formwork+rebar to be hidden) → concrete pour (дневник)
        → обр.8 (after strip, ≥N days) → обр.7 (level accepted) → next level
  → обр.14 (structure accepted — "груб строеж" gate; requires the chain above)
  → finishing works, installations → test protocols ("акт 17", контроли)
  → обр.15 (ready for handover; huge inventory of everything above)
  → окончателен доклад + технически паспорт
  → удостоверение за въвеждане в експлоатация (cat IV–V) / ДПК+обр.16 (I–III)
Suspension at any point: обр.10; resumption: обр.11 (seen on builder change).
```

The combined sample file is exactly one such chain for the structural phase —
9 pours' worth of обр.12/8/7 triplets. This is the workflow engine's ground
truth ([14_WORKFLOW_ENGINE.md](14_WORKFLOW_ENGINE.md)).

## 6. Fact anatomy (what a "value" is here)

From the samples, recurring fact families:

- **Identification**: строеж name (verbose, quoted), category + legal basis,
  cadastral identifiers (ПИ, сграда, кад. район), administrative address,
  местност/план.
- **Permit**: РС №, date, issuer (Главен архитект на …), approval dates of
  the investment project, list of approved parts.
- **Participants**: as §3, with their document numbers and validity dates.
- **Chronology**: dates of every act, contracts, orders, suspensions.
- **Works & quantities**: per-act tables — наименование СМР, ед. мярка,
  проектно/изпълнено количество, оценка (обр. 7/12); concrete class, volume,
  pour date, curing days (обр. 8/12); reinforcement by steel class & diameter
  with kg/m pairs (обр. 7 tables).
- **Technical characteristics** (passport): areas (ЗП/РЗП), volumes, heights,
  floors, construction system, fire class, energy class.
- **Certificates**: декларации за експлоатационни показатели per material,
  контролни протоколи with numbers/dates/issuers.
- **Narrative blocks**: per-part descriptions in Act 15 (architecture,
  structure, installations) — these are *composed prose*, the one place AI
  drafting (from structured inputs, human-approved) legitimately helps.

## 7. Defect classes observed in real documents

These calibrate the consistency engine ([19_VALIDATION](19_VALIDATION_AND_CONSISTENCY.md)):

1. **Identifier drift** — the sample technical passport carries two
   different ПИ identifiers in its header and a third, unrelated one in
   §1.4 (values withheld here — real property identifiers; the anonymized
   fixture reproduces the pattern with synthetic ids).
2. **Wrong-form boilerplate** — combined file: header "Ак образец 7", body
   title is обр. 12's ("…подлежащи на закриване…").
3. **Chronology errors** — 2021 protocol with an embedded table dated 2020;
   "20.04.12.2021" malformed date in Act 15's inventory.
4. **Typos in legal identifiers** — "02.09.202г.", "Агенцията па геодезия".
5. **Cross-document mismatches waiting to happen** — a mid-project builder
   change means half the documents name builder-1 and half builder-2; only
   обр. 10/11 legitimize the switch — a rule must know that.

## 8. Verification obligations (open)

Normative details asserted here from memory/practice **must be verified
against the current consolidated texts** (Наредба №3 has been amended; form
numbering and required signatories change): exact obligatory participant set
per form, current обр. 17 meaning, minimum decofring waiting periods, ДПК
composition. Tracked as [29_RISKS Q1](29_RISKS_AND_OPEN_QUESTIONS.md). The
architecture already assumes this volatility: forms live in the data-driven
document-type registry, not in code (ADR-CS-007).
