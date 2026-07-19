# ADR-CS-007 — Document-type registry as data, not code

Status: Proposed (PO review) · Date: 18.07.2026

## Context

Three facts about the domain's naming and evolution:
1. Practice diverges from regulation — the firm's "акт-17" files are
   72-hour installation test protocols, which is not what Наредба №3's
   обр. 17 denotes; colloquial numbering is entrenched.
2. Regulations get amended — forms, required signatories, and numbering have
   changed over the years and will again ([02 §8](../02_DOMAIN_KNOWLEDGE_BIBLE.md)).
3. The form catalog is long-tailed — dozens of acts/protocols, most rare;
   hard-coding each as a Python class would make every regulatory tweak a
   release.

## Decision

1. Document types are **registry rows** (`cs_document_types`): internal
   stable key (`act_12`, `act_14`, `test_protocol_72h`…), normative citation,
   **practice aliases**, applicable categories, required roles, links to
   template versions, rule sets, workflow definitions, dossier ordering.
2. Code never branches on "act number"; it consumes registry attributes.
   Type-specific behavior beyond what the registry + rule kinds express is
   the *exception*, implemented behind a registry-declared behavior key.
3. Adding a standard form = registry data + template pair + rule set —
   zero code (tested property, [30 AC-7](../30_ACCEPTANCE_CRITERIA.md)).
   New *rule kinds* or *behavior keys* remain code (ADR-CS-003 discipline —
   no logic-in-data eval).
4. Registry entries are versioned once referenced by issued documents
   ([22 §1](../22_AUDIT_AND_VERSIONING.md)).

## Consequences

- Regulatory amendments and practice quirks are absorbed as data changes
  with effective dates; historical documents keep their historical forms.
- Search/UX must handle aliases ("акт 17" finds `test_protocol_72h`).
- The registry becomes review-worthy data — seed migrations for built-in
  types are reviewed like code, because they are the product's legal
  vocabulary.
