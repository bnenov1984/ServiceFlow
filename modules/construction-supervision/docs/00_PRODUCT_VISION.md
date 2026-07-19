# CS-00 — Product Vision

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `construction-supervision`

## 1. The problem

A Bulgarian construction supervision company (консултант, упражняващ
строителен надзор) shepherds every construction project through a legally
mandated paper trail: Наредба №3/2003 acts and protocols (обр. 2…17), the
final report (окончателен доклад, чл. 168 ал. 6 ЗУТ), and the technical
passport (Наредба №5/2006). Analysis of a real single-family-house project
(see [samples/](../samples/README.md)) shows:

- **~20+ acts for one small (category V) house** — a chronological chain of
  обр. 12 (hidden works) → обр. 7 (structural levels) → обр. 8 (post-formwork
  concrete state) per pour, plus обр. 2, 3, 5, 6, 10, 11, 14, 15, installation
  test protocols, and the technical passport.
- **The same ~15 facts repeated in every document header**: project name,
  category, cadastral identifier, permit number/date/issuer, and five-plus
  participants with their companies, EIK numbers, license/diploma numbers.
- **Real drift**: in the sample set the technical passport carries *two
  different cadastral identifiers* in the same document; an act labelled
  "образец 7" carries the body text of обр. 12; a 2021 protocol contains a
  table dated 2020. These are not hypothetical risks — they are in the firm's
  actual output today.

Every document is currently produced by copy-paste-edit of a previous Word
file. The cost is hours of clerical work per project and a standing legal
exposure: acts with inconsistent data can stall commissioning (въвеждане в
експлоатация) or surface in ДНСК inspections.

## 2. The vision

**The project exists exactly once.** One structured knowledge base holds every
fact about a construction project — identification, permit, participants,
phases, executed works, quantities, certificates — each fact with provenance
(source document, page, extraction method, confidence, correction history).

**Documents are views.** Act 12, Act 14, Act 15, the technical passport, and
every future document type are *generated* from the knowledge base through
versioned templates. Change the permit number once; every not-yet-issued
document that shows it is regenerated correctly. Issued documents are
immutable snapshots — history, not live views.

**The core is deterministic.** Given the same knowledge base and template
version, generation is byte-reproducible. AI never sits between the data and
the document.

**AI is a reader, not an author.** AI extracts candidate facts from imported
PDFs, scans, and drawings, flags inconsistencies, and drafts predefined
engineering paragraphs — always as *proposals* that a human confirms before
they become facts. AI never invents values (see
[20_AI_STRATEGY.md](20_AI_STRATEGY.md), ADR-CS-003).

## 3. Who it is for

Primary: small Bulgarian supervision firms (1–10 engineers) — the same size
class as ServiceFlow's shops, matching the Business OS pragmatism directive.
The buyer is the firm's manager (управител, holder of the ДНСК
удостоверение); the daily users are the supervising engineers per project
part (Архитектурна, Конструктивна, Електро, ВиК, Геодезия, ЕЕ, ПБ) and office
staff. Secondary (later): builders' technical managers and designers as
external signatories/viewers.

## 4. Value proposition

1. **Hours → minutes** per document: header blocks, participant lists, and
   document inventories (the long "прегледахме следните документи" sections of
   Act 14/15) assemble themselves from the knowledge base.
2. **Zero-drift guarantee**: one fact, one place; the consistency engine
   ([13_RULES_ENGINE.md](13_RULES_ENGINE.md)) makes drift a detected finding
   instead of a discovered embarrassment.
3. **A living dossier**: at any moment the firm sees which acts exist, which
   are missing for the next phase gate (e.g. Act 14 requires the chain of
   обр. 12/7/8 for the structure), and what blocks Act 15.
4. **Institutional memory**: the knowledge base + audit trail outlives staff
   turnover and survives ДНСК scrutiny with full traceability.

## 5. What this product is NOT

- Not an AI chatbot; not a text generator. (ADR-CS-003)
- Not a CAD tool, a structural analysis package (Tower, SAP2000), or a BIM
  platform — it *reads* their outputs, it does not replace them.
- Not a construction ERP (no budgeting, procurement, payroll).
- Not a document management system for arbitrary files — files matter only as
  sources of facts and members of the dossier.
- Not a legal-form editor: the normative content of the acts comes from
  Наредба №3; the system fills them, it does not reinterpret them.

## 6. Success criteria (product level)

- A supervision firm produces a complete, internally consistent act chain for
  a category V house with **no fact typed twice**.
- Act 12, Act 14, Act 15, and the technical passport generated from the
  knowledge base are accepted in real administrative procedures unchanged.
- The consistency engine catches 100% of the defect classes found in the
  sample set (identifier drift, wrong-form boilerplate, chronology violations)
  on the samples themselves ([30_ACCEPTANCE_CRITERIA.md](30_ACCEPTANCE_CRITERIA.md)).
- The module runs on Business OS Core with zero modifications to ServiceFlow
  domain modules — the Business OS platform proof (BOS-00 §9).
