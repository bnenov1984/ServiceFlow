# PS-17 — Document Dossier

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Two distinct concepts, deliberately separated: **document requirements**
(what inputs the assignment needs — a state machine) and **dossier files**
(what bytes we hold — storage records). Conflating them is how "missing
documents" stops being computable.

## 1. Document requirements (FR-PS-060)

`DocumentRequirement`: assignment_id, name ("Скица от КККР"), state
`missing → requested → received | waived`, requested_on, received_on,
optional linked file_id, note.

- Instantiated from the service type's default requirements list at intake
  (copy semantics as everywhere); add/remove ad hoc per assignment.
- `missing`/`requested` requirements = the assignment's missing-documents
  set → dashboard bucket "Чакащи документи" (with I-5 catching un-chased
  waits) and the J-4 chase loop.
- `received` requires either a linked file or an explicit "получен на
  хартия" note — reality includes paper.
- `waived` (не е необходим за този случай) keeps templates honest without
  fake receipts. All state changes audit-logged.

## 2. Dossier files (FR-PS-061)

`DossierFile`: assignment_id, category (fixed ten: `incoming`, `working`,
`photos`, `calculations`, `draft`, `delivered`, `signed`, `invoice`,
`correspondence`, `other`), filename, storage_key, content_type, size,
uploaded_by/at, optional note, soft-deleted flag (+version fields, P).

- Storage via the **Core storage port** (ADR-007 — directly reusable;
  verdict R-CORE in [27]). This module does **not** reuse ServiceFlow's
  attachments pipeline (order-anchored, re-encode/thumbnail machinery sized
  for phone photos of devices — BOS-02 group D). MVP uploads bytes as-is;
  image thumbnailing is P, and if built, built module-side (extraction of
  a shared pipeline is a Phase-6 comparison, not an MVP dependency).
- Fixed categories, not org-configurable folders: ten covers the domain
  ([03] evidence), keeps UI/filters/tests enumerable, and dodges the
  folder-taxonomy rabbit hole. Org-specific nuance goes in filename/note.
- Preview: browser-native only (images, PDFs) — FR-PS-062. Download always.
  Delete = soft (uploader same-day or manager+), audit-logged; files in
  category `delivered`/`signed` on a completed assignment never delete
  ([26] INV-11 corollary).
- Size limits and allowed types: platform defaults (config), generous —
  professionals mail 200-page scans.

## 3. Versioning (P) and history

MVP: re-upload = new file row; humans name versions (v2, финал…). P:
`version_of` chain + "предишни версии" collapse in UI (FR-PS-063). Full
byte-diff comparison: F-class, likely never (professionals compare content,
not bytes).

## 4. Boundary with specialised document modules

This dossier is a **filing cabinet**: it stores, categorises, links, and
serves bytes. It never understands content. Specifically versus
Construction Documentation ([29]):

- CS *generates* acts/passports from its knowledge base; those outputs live
  in **CS's** storage under CS's provenance rules.
- A PS assignment linked to a CS project shows CS deliverables via the read
  contract (list + fetch-by-reference) — **no file copying between
  modules**; the dossier holds only what users upload to the assignment.
- Future OCR/extraction/AI-summaries (F) would be PS-side conveniences on
  PS-uploaded files only; anything act-shaped belongs to CS.

## 5. Privacy note

Files contain deep PII by nature ([16] §4). MVP posture: access control +
audit (who downloaded what is logged at the platform access-log level, not
as business events), no content scanning, honest help-text in settings.
Retention follows the firm's professional obligations; the module deletes
nothing on its own.
