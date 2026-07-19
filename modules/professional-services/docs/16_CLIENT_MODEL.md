# PS-16 — Client Model

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

This module **owns its Client** (`ps_clients`) — it does not share
ServiceFlow's `customers` table or a hypothetical platform Party model
(ADR-PS-003; BOS-02 explicitly rejects promoting a shared Contact/Party now).
Extraction of a shared model is a Phase-6 platform question, answerable only
once two concrete implementations exist.

## 1. Why not reuse ServiceFlow customers (evidence, not taste)

Inspected: `serviceflow/customers/` + BOS-02/BOS-03. ServiceFlow's Customer
is phone-first, walk-in-shaped (normalized-phone duplicate detection,
transliteration shadow columns, repair-shop GDPR flows) and lives inside
ServiceFlow's data-ownership boundary — cross-module table writes are
forbidden (BOS-04/05). This module's client is institution-first (courts,
banks, municipalities — entities with departments, contact persons, EIK,
long-running relationships). Forcing one table would couple two verticals
on their most divergent entity and violate the platform's own rules. Cost
accepted: a firm running both modules (unlikely persona overlap) enters a
client twice.

## 2. Entity

**Client** (`ps_clients`): `kind ∈ {person, organization}`, name (required —
the only required field, J-1), phones (list), emails (list), address (one
free-text — no structured address model, BOS-02 "do not invent"), `eik`
(organizations; optional; format-validated when present), notes,
`communication_preference` (free note, e.g. "само по email"), active flag,
anonymized flag. **No ЕГН/personal-identifier column by default** (§4).

**ClientContact** (`ps_client_contacts`): client_id, name, role ("кредитен
инспектор"), phone, email, active. Assignments may reference one as the
contact person for that engagement.

Client kinds cover the commissioned org spectrum (courts, banks, companies,
municipalities, individuals) without subtype tables — what varies (case
numbers, branch codes) belongs to the *assignment's* typed details, not the
client.

## 3. Behaviour

| # | Rule |
|---|---|
| C-1 | Inline minimal creation from intake (name + phone) — J-1 ⚡; enrichment later |
| C-2 | Duplicate hint (P): normalized name (shared_kernel normalization primitives — Core, directly reusable) + phone match on create; hint, never a block |
| C-3 | Client detail aggregates: assignments (state, deadlines, risk), money summary (derived, [21]), communications across assignments |
| C-4 | Deactivation hides from pickers; history intact. Hard delete only when zero assignments ever existed |
| C-5 | One client, many concurrent assignments of any service types — no constraint, by design |

## 4. GDPR & data minimisation (commissioned analysis)

- **Lawful basis:** contract performance for client data on assignments;
  legitimate interest for the communication log. Nothing here needs consent
  flows in-product; the firm is controller, the platform processor
  (platform DPA — Етап-3 scope, noted in [28]).
- **ЕГН (personal identifier): not stored by default.** No column ships
  enabled. Justified need (e.g. court requires it in the expert report):
  org-level opt-in setting exposes an `personal_identifier` field on person
  clients, stored in a separate column, visible only to manager+, flagged
  in export. The default answers the commission's minimisation requirement;
  the opt-in answers reality. (ADR-PS-003 records this.)
- **EIK is not personal data** (company identifier) — safe default field.
  ЕТ (sole traders) blur this; treated as organizations, EIK allowed.
- **Anonymization (person clients):** replaces name/phones/emails/address/
  notes with placeholders, sets anonymized flag, and opens a guided review
  of that client's assignment titles/descriptions for identifying strings
  (human-confirmed edits — deterministic scrubbing of free text is a lie we
  refuse to sell). Assignment records, numbers, money, history survive
  (INV-6). Pattern follows ServiceFlow's proven approach — **pattern reuse,
  own implementation** ([27] verdict R-PAT).
- **Files may contain deep PII** (нотариални актове, ЕГН inside PDFs). Not
  scanned in MVP; retention is the firm's professional obligation. The
  dossier notes this in-UI at upload? — no: one line in org settings/help,
  not per-upload nagging ([17] §5). Export includes files (they are the
  client's data too).
- No PII in logs (NFR-PS-11); communication log stores business facts, not
  message bodies from integrations (there are none in MVP).

## 5. Client ↔ assignment integrity

- Assignment requires a client (INV-2 family); client with assignments
  cannot be hard-deleted (C-4, INV-6).
- Client merge (duplicate cleanup) is P: reassign assignments to the
  surviving client, audit-logged; MVP lives with C-2's prevention.
