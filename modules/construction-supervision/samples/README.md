# Samples

Real-world domain documents used as analysis inputs, template sources, and
(anonymized) test fixtures. **Local source documents were reviewed during
domain discovery but are intentionally excluded from the repository because
they contain personal and confidential data** (names, addresses, credential
numbers, property identifiers, signatures). They remain in the PO's local
working folder. Before committing any sample here: anonymize names, ЕГН-like
numbers, ЕИК, cadastral identifiers, addresses, and signatures.

## Known source corpus (as of 18.07.2026 discovery — held locally, not committed)

| Source (generic description) | What it is | Feeds |
|---|---|---|
| Act 14 template + filled instance (project A — category V house) | Приемане на конструкцията | act_14 template pair, golden fixture |
| Act 15 filled instance (project A) | Годност за приемане | act_15 template pair, golden fixture |
| Technical passport, filled (project A) | Наредба №5 passport | technical_passport template, **identifier-drift defect fixture** |
| Combined chronological bundle: ~20 acts обр. 12/7/8 (project A structural phase, 9 pour cycles) | скрити работи / нива / декофриране chain | act_12/7/8 extractors, splitting tests, **обр.7-header/обр.12-body defect fixture** |
| Act 12 variants per part (Ел / ВиК / Арх) | обр. 12 part variants | act_12 part-scoped templates |
| 72-hour test protocols, ВиК and Ел variants (practice name "акт 17") | инсталационни изпитания | test_protocol_72h, alias handling, **2020/2021 chronology defect fixture** |
| Act 15 / technical passports (project B — second category V house) | second project | cross-project variance checks |

## Directory purpose

- `source-documents/` — anonymized originals (PDF/DOCX/scans) as imported.
- `annotated-documents/` — same documents with extraction annotations
  (expected fields, anchors) for extractor/AI evaluation.
- `template-examples/` — placeholder-ized visual templates + their manifests.
- `expected-outputs/` — golden generated DOCX per template version + fixture
  dataset (byte-normalized) for determinism tests.

Wanted next (open — [29 Q2](../docs/29_RISKS_AND_OPEN_QUESTIONS.md)):
construction drawings with schedules, a permit (РС) original, обр. 2/3/5/6
instances, дневник на бетоновите работи, a cat I–III project's set.
