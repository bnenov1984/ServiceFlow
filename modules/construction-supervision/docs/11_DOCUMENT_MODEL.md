# CS-11 — Document Model

Status: Draft · Date: 18.07.2026 · The catalog below is grounded in the real
sample set ([samples/](../samples/README.md)); field lists name the *data
requirements*, exact wording stays in templates.

## 1. Principles

1. **One form = one document type** (ADR-CS-005). Packaging in source files
   (the combined актове-къща.docx) never defines types.
2. Every type declares: purpose, trigger, required participants (signatories),
   data bindings, table sections, rule set, workflow, dossier position.
3. Recurring types (обр. 7/8/12) are *instance families*: many instances per
   project, each with subject label ("кофраж и армировка основи") and its own
   chain position.
4. All types share the **common header block** (строеж, местонахождение,
   възложител, строител, техн. ръководител, консултант, проектант част …) —
   bound once in the manifest library, rendered per template. This block is
   where today's copy-paste drift lives; here it is one binding set.

## 2. MVP document types (full treatment)

### 2.1 `act_12` — Акт обр. 12 (скрити работи)

- **Purpose/trigger**: before covering any works; recurs per covered scope.
- **Signatories** (from samples): техн. ръководител, възложител, проектант
  (съотв. част), консултант/СН. Part-scoped (СК, Ел, ВиК, Арх variants exist).
- **Data**: common header + part; date; scope description ("…които подлежат
  на закриване – <scope>"); **works table**: rows (наименование СМР, ед.
  мярка, проектно кол-во, изпълнено ед. мярка + кол-во, оценка/забележка);
  closing statements: acceptance sentence + разрешение for the next operation
  (e.g. "разрешава наливането на В25"); optional instruction lines (curing
  period, "да се състави обр. 8").
- **Rules**: table rows ≥1; units from unit vocabulary; изпълнено vs проект
  deviation → warning; next-operation authorization consistent with workflow;
  date within active construction period (not suspended per обр. 10/11).
- **Workflow**: draft → ready → prepared → issued; issuance feeds the Act 14
  gate for structural instances.

### 2.2 `act_14` — Акт обр. 14 (приемане на конструкцията)

Modeled fully independently (explicit requirement + ADR-CS-005).

- **Purpose/trigger**: acceptance of the load-bearing structure; the груб
  строеж gate; once per project (or per stage/етап).
- **Signatories** (sample): проектант-конструктор, строител (управител),
  техн. ръководител, консултант/СН по част Конструктивна. Note the *different
  cast* from Act 12/15 — a per-type required-roles declaration, not shared.
- **Data**: common header; date; **reviewed-documents inventory** (permit,
  approved parts+dates, СМР contract(s) + техн. ръководител credentials +
  appointment order, обр. 2 protocol, заповедна книга №/дата, обр. 3/5/6
  acts, the обр. 7 and обр. 12 series, дневник на бетоновите работи,
  material certificates) — **auto-composed from the dossier**, not typed;
  findings §: constatations (изпълнение съответства…; частични недостатъци);
  **conclusion**: fixed normative paragraph + разрешение за довършителни работи.
- **Rules (gate)**: all structural обр. 12/7/8 instances issued; обр. 2/3/5/6
  present (category-dependent); дневник referenced; no open blocker findings
  on structural facts; date after the last structural act.
- **Output**: own DOCX template; own numbering.

### 2.3 `act_15` — Акт обр. 15 (годност за приемане)

- **Purpose/trigger**: builder→client handover after completion, before
  commissioning steps.
- **Signatories** (sample): възложител; проектанти **по всички части**
  (named per part with credentials); строител + техн. ръководител(и);
  консултант + специалисти СН по части — the largest cast; supports multiple
  builders sequentially (sample has two with disjoint contracts).
- **Data**: common header; date; reviewed documents (permit, projects,
  contracts with credentials); **per-part narrative sections** (Архитектурна,
  Конструктивна, Електро, ВиК, Геодезия, ПБ, ЕЕ — composed prose from
  structured inputs + approved free text); site/surroundings state;
  РЕШИХМЕ conclusion; **numbered inventory of the entire dossier**
  (обр. 2…14, дневници, protocols, скици, декларации) — auto-composed;
  handover clause.
- **Rules (gate)**: Act 14 issued; installation test protocols present per
  installed systems; ПБ становище present; inventory complete vs dossier;
  chronology (after everything it lists); all participants' credentials valid
  at date.

### 2.4 `technical_passport` — Технически паспорт (Наредба №5)

- **Structure** (sample follows the normative приложение): Част А раздели
  I–V (identification & parameters; обемнопланировъчни показатели; technical
  characteristics по чл. 169; сертификати; съставители), Част Б (мерки за
  поддържане, срокове), Част В (указания за безопасна експлоатация).
- **Data**: overwhelmingly *reuse*: identification, permit chain, documents
  list (обр. 16/уведомления, окончателен доклад refs), participants with
  credentials (§5), certificates inventory (§IV — the long декларации list,
  auto-composed from ingested certificates), плюс passport-specific
  characteristics (areas, volumes, heights, конструктивна система, fire
  class, energy class) entered once as facts.
- **Rules**: identifier consistency (the sample's real defect class №1);
  registration fields (рег. №/дата) filled at issuance; §IV inventory matches
  ingested certificates; category-consistent content.
- **Note**: passport has its own registration flow with the municipality —
  workflow includes `registered` beyond `issued`.

## 3. Catalogued for later phases (registry entries from day one, templates later)

| Type key | Form | Phase | Notes |
|---|---|---|---|
| `act_2`, `act_2a` | откриване стр. площадка, линия и ниво | B | referenced by everything; simple fixed form |
| `act_3` | съответствие със строителните книжа | B | |
| `act_4_order_book` | заповедна книга | C | running log, different UX (entries, not one-shot doc) |
| `act_5` | уточняване на терена/репер | B | |
| `act_6` | земна основа и коти изкоп | B | |
| `act_7` | СМР по нива и елементи | **B** | sample-backed; instance family like обр. 12 |
| `act_8` | декофриран бетон | **B** | sample-backed; curing-period chronology rules |
| `act_10`, `act_11` | спиране/продължаване | B | builder-change evidence |
| `test_protocol_72h` | 72-час. проби (ВиК/Ел variants) | B/C | practice "акт 17" naming → aliases (ADR-CS-007) |
| `concrete_log` | дневник на бетоновите работи | C | structured log feeding обр. 8/12/14 rules |
| `final_report` | окончателен доклад чл. 168(6) | C | large composed report; heavy dossier reuse |
| `act_16_dpk` | ДПК протокол (cat I–III) | D+ | no sample; needs client evidence |
| `energy_certificate`, `екзекутиви`, misc protocols | — | as ingested sources first | generation only if a client asks |

Act 7 and Act 8 are **not MVP** for generation (the MVP targets the four
types above) but their *ingestion and modeling* matter from phase B because
Act 14's gate consumes their chain. Decision recorded here per the task
brief: обр. 7, обр. 8 → phase B; обр. 16, окончателен доклад → later; the
"акт 17" protocols → B/C with alias handling.

## 4. Document instance states

`draft` (regenerable) → `ready` (validation gate passed) → `prepared`
(handed out for signing; content locked) → `issued` (signed on date, snapshot
frozen, number assigned) → `superseded` (formal replacement, reason required).
`technical_passport` adds `registered`. Transitions: single endpoint, logged
(FR-9.1), definitions in [14_WORKFLOW_ENGINE.md](14_WORKFLOW_ENGINE.md).
