# PS-31 — Localisation Strategy

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

## 1. Baseline (platform mechanism, ADR-015 — consumed as-is)

- Docs and code in English; **all** user-facing copy in Bulgarian from the
  frontend catalog; backend returns `message_key` + params, never prose.
- Module namespace: every key starts `ps.` (BOS-06 i18n field); catalog
  lives with the module's frontend features and merges into the app
  catalog at build time.
- English-ready: adding an `en` catalog is content work only (NFR-PS-24).
  No translation planned for MVP.

## 2. The module's one special problem: the configurable label

The org chooses what an Assignment is called (Поръчка/Досие/Преписка…,
ADR-PS-004). Mechanics:

- Org setting `ps.assignment_label` stores a **label pack**: singular,
  plural, and — because Bulgarian morphology will not be defeated by string
  concatenation — the shipped choices are a **closed list** of packs with
  correct forms (Поръчка/Поръчки/поръчката/нова поръчка …), not free text.
  Free-text label (org types its own) is P and accepts grammatical
  imperfection explicitly when chosen.
- Catalog strings reference `{label}`/`{label_plural}`/… placeholders;
  the i18n layer injects the pack. Keys never change with the label
  ([04] §4.1).
- Fixed vocabulary (lifecycle states, stage categories, risk labels,
  communication types) is **not** configurable — one firm's Спешно must
  mean every firm's Спешно, or support and documentation die.

## 3. Formats

- Dates: `дд.мм.гггг` display and typed input ([22] §4); weekday names in
  Bulgarian; calendar weeks start Monday.
- Times: 24-hour. Timezone: Europe/Sofia ([13] §2), invisible to users.
- Numbers/money: `1 234,56`; currency shown as лв./BGN (EUR-ready via the
  currency column, [21] §1; display switch is content work when the
  transition date matters).
- Sorting/search: Bulgarian collation; shared_kernel normalization for
  search/dup-matching (handles Cyrillic/Latin mixing — Core capability).

## 4. Content quality rules

- Tone: professional, short, no diminutives, no exclamation marks; error
  texts always state the fix ("Изберете вид услуга, за да продължите").
- Domain terms follow the glossary's BG column ([04]) — the catalog is
  reviewed against it (consistency check in the docs review and again at
  catalog-review time).
- Legal-flavoured strings (GDPR notices, anonymization warnings) get PO
  review before ship; the module never generates legal advice.

## 5. Testing hooks ([32] §T-9)

Catalog completeness test (every `ps.*` key referenced in code exists in
bg catalog; no orphans); label-pack substitution test (no raw `{label}`
leaks); message-key test (no literal Cyrillic in backend responses);
pseudo-locale smoke for layout overflow (long German-length words) — cheap,
catches truncation.
