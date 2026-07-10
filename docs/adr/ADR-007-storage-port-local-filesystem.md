# ADR-007 — Storage Port over Local Filesystem

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §D7, 06 §C4

## Context
Attachments (photos dominate: 50–100 GB over 3 years worst case) must be stored
locally in V1, included in the verified backup artifact, and move to S3-class object
storage in SaaS without domain changes.

## Decision
Domain and API reference attachments only via **storage keys** through a storage
port (interface): `put / get / delete / exists / stream`. V1 implementation: local
filesystem, content-addressed layout (hash-based paths → free deduplication and the
incremental file backup in 05 §1). No absolute paths anywhere in domain data
(migration constraint C4). Access to files always flows through the application
(authenticated, logged) — never direct file shares.

## Alternatives considered
- **Blobs in PostgreSQL** — single backup artifact is tempting; rejected: DB bloat,
  memory pressure, slow dumps at photo volumes.
- **Local MinIO (S3 API today)** — API parity now, but a third service on the shop
  PC for zero V1 benefit; the port provides parity at the interface level. Rejected.

## Consequences
- **Advantages:** trivial ops; fast LAN serving; content addressing powers backup
  incrementality and integrity checksums; SaaS swap is one adapter.
- **Disadvantages:** filesystem quirks (AV scanning, path length, locking) are ours
  to handle; two things to back up (DB + files) — unified by the single artifact.
- **Risks:** disk-full on shop PCs. Mitigation: health disk-space monitoring with
  plain-Bulgarian warnings; photo re-encoding caps sizes (02 §9).

## Reconsideration triggers
SaaS implementation (S3 adapter); or V1.5 features needing signed direct URLs.
