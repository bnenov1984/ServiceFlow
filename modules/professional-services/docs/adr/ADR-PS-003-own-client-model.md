# ADR-PS-003 — Module-owned Client model; no shared Party

Status: **Proposed** · Date: 18.07.2026

## Context

The commission says clients "should be shared with Business OS where
technically and conceptually appropriate". Verified: the platform has **no
shared client capability** — BOS-02 classifies ServiceFlow's Customer as
group C (vertical-owned) and explicitly **rejects** promoting a shared
Party/Contact model now. ServiceFlow's Customer is phone-first and
repair-shop-shaped; this module's clients are frequently institutions
(courts, banks, municipalities) with contact persons and EIK.

## Decision

- This module owns **`ps_clients`** + `ps_client_contacts` (PS-16): kinds
  person/organization, institution-friendly fields, contact persons.
- **Data minimisation:** no personal-identifier (ЕГН) column active by
  default; org-level opt-in enables it for firms with a documented business
  need (e.g. court requirements), visible manager+, flagged in export.
- GDPR erasure = anonymization preserving business records (INV-6), with
  guided free-text review — the ServiceFlow *pattern*, own implementation.
- No reconciliation with ServiceFlow customers in v1; a shared platform
  client capability is a Phase-6 extraction question, answerable from two
  real implementations.

## Consequences

- A firm running both verticals enters a client twice — accepted; the
  persona overlap is near-zero and the alternative (premature shared
  schema) poisons both modules.
- The module's client table becomes the second data point for any future
  extraction — its shape is documented with that comparison in mind.
- EIK stays a plain optional field (company identifier, not personal data);
  ЕТ edge treated as organizations.
