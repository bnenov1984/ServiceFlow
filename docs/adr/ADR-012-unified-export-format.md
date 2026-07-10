# ADR-012 — One Versioned Export Format: Backup = GDPR Export = SaaS Migration

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 05 §1, 06 §C2/C7

## Context
Three obligations need a complete, portable representation of a company's data:
nightly verified backups (05), GDPR/company data export, and the future Local→SaaS
migration payload (06). Three formats would mean three test surfaces and guaranteed
drift.

## Decision
One versioned artifact format: full database dump + content-addressed attachment
files (logically complete, physically incremental) + configuration/license state +
manifest (app & schema & format versions, entity counts, per-file checksums). Format
version embedded; every consumer (restore wizard, SaaS importer, CI harness)
maintains an upgrade chain covering **all** published format versions, forever
(constraint C7). From V1's first release, CI proves every format version still
imports (06 §6.2).

## Alternatives considered
- **Separate formats per purpose** (pg_dump for backup, JSON for GDPR, custom for
  migration) — each format tested less, migration correctness unproven until V2.
  Rejected.
- **Plain pg_dump alone** — no files, no manifest, no integrity story, not
  self-describing. Rejected as insufficient rather than wrong (it lives *inside* the
  artifact).

## Consequences
- **Advantages (the keystone):** migration correctness is rehearsed nightly in every
  shop by the restore-verifier — the SaaS importer consumes a format with thousands
  of real-world verification runs behind it. One test surface, three obligations.
- **Disadvantages:** format changes carry ceremony (version bump + importer step +
  test artifact, every time — 06 §6.3).
- **Risks:** format ossification discouraging schema evolution. Mitigation: the
  format tracks the schema via the same Alembic chain; ceremony is a checklist, not
  a redesign.

## Reconsideration triggers
None foreseeable — this ADR is the migration strategy's foundation. Amendments only
via the C-constraint change process (freeze rules in 07_ADR_INDEX).
