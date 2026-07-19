# PS-18 — Communication Log

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Manual, honest, three-clicks-fast. Solves P10 (lost history) and feeds P4
(client asks for update → open assignment → read the log).

## 1. Entity

`CommunicationEntry`: assignment_id, type (`call`, `email`, `meeting`,
`client_visit`, `court_communication`, `message`, `internal_note`,
`document_request`, `delivery_confirmation`), direction `in | out | none`
(internal notes have none), occurred_at (defaults to now, editable — calls
get logged after lunch), note (free text), created_by/at, optional
client_contact_id (who we spoke to).

The nine types are the commissioned list verbatim; they are code-owned
(enumerable filters, i18n keys), not org-configurable — a tenth type has no
evidence, "other" ≈ `message`.

## 2. Quick-entry design (the ≤3-interaction budget, FR-PS-070)

- Entry points: assignment detail (S-4) — always-visible "Запиши
  комуникация" row: [type icons] [бележка…] [Запиши]; type defaults to
  `call`, direction toggles in the row, note optional. One line + Enter =
  logged. Dashboard/list rows offer the same via row action (J-2 step 3).
- The row never opens a modal for the common case; occurred-at and contact
  person are behind "още" (progressive disclosure).
- Logging a communication counts as activity (resets I-1 staleness) and
  optionally chains: "запиши и задай следваща стъпка" — the J-4 combo
  (log the call, set the chase date) in one flow.

## 3. Presentation

- Assignment detail: chronological feed **merged with activity events**
  (one story: "звъняхме → преместена в Оглед → качен файл"), filter chips
  to isolate communications (FR-PS-071).
- Client detail: communications across all the client's assignments (C-3).
- `internal_note` entries are visible to all module users of the tenant in
  MVP (small-firm transparency; per-role hiding is scope creep with no
  requesting persona — revisit only with the >5-people permission trigger,
  [02] §3).

## 4. Deliberate non-features

- **No integrations in MVP or their prerequisites** (no email parsing,
  no calendar sync, no Viber bots): F-class with a named trigger ([34]).
  The model is integration-ready by shape (type + direction + occurred_at +
  note covers an ingested email's envelope), which costs nothing now.
- **No message bodies**: the log records that/what-about, not transcripts.
  Paste-into-note is the user's choice; the product never encourages
  storing correspondence wholesale (privacy posture, [16] §4).
- **No read-receipts/threading/mentions** — it is a logbook, not a chat.
